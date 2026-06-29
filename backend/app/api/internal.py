from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.orders import sync_account_orders
from ..database import get_db
from ..models.account import Account
from ..models.order import Order
from ..services.delivery import DeliveryExecutor

router = APIRouter(prefix="/internal", tags=["internal"])


class OrderEventRequest(BaseModel):
    account_id: str
    order_id: str
    item_id: str = ""
    buyer_id: str = ""
    buyer_name: str = ""
    price: float = 0
    status: str = "paid"
    auto_deliver: bool = True


@router.post("/delivery/orders/{order_id}/deliver")
async def internal_deliver_order(order_id: str, db: AsyncSession = Depends(get_db)):
    order = (await db.execute(select(Order).where(Order.order_id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    log = await DeliveryExecutor(db).deliver_order(order)
    return {"success": log.status == "success", "status": log.status, "error": log.error}


@router.post("/orders/sync")
async def sync_orders_internal(
    query_code: str = Query("NOT_SHIP"),
    max_pages: int = Query(3, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    accounts = (await db.execute(select(Account).where(Account.status == "active"))).scalars().all()
    return await sync_account_orders(db, accounts, query_code, max_pages)


@router.post("/orders/event")
async def upsert_order_event(data: OrderEventRequest, db: AsyncSession = Depends(get_db)):
    if not data.account_id or not data.order_id:
        raise HTTPException(status_code=400, detail="account_id和order_id不能为空")

    order = (await db.execute(select(Order).where(Order.order_id == data.order_id))).scalar_one_or_none()
    if not order:
        order = Order(order_id=data.order_id, account_id=data.account_id)
        db.add(order)
    order.account_id = data.account_id
    order.item_id = data.item_id or order.item_id
    order.buyer_id = data.buyer_id or order.buyer_id
    order.buyer_name = data.buyer_name or order.buyer_name
    order.price = data.price or order.price or 0
    order.status = data.status or order.status or "paid"
    await db.commit()
    await db.refresh(order)

    delivery = None
    if data.auto_deliver and order.status in ("paid", "pending"):
        delivery = await DeliveryExecutor(db).deliver_order(order)

    return {
        "success": True,
        "order_id": order.order_id,
        "delivered": bool(delivery and delivery.status == "success"),
        "delivery_status": delivery.status if delivery else "",
        "error": delivery.error if delivery else "",
    }
