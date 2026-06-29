from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from ..database import get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.order import Order
from ..models.user import User
from ..utils.order_fetcher import OrderFetcher

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderResponse(BaseModel):
    order_id: str
    account_id: str
    item_id: str = ""
    buyer_id: str = ""
    buyer_name: str = ""
    price: float = 0
    status: str = "pending"
    is_rated: bool = False

    class Config:
        from_attributes = True


async def sync_account_orders(db: AsyncSession, accounts: list[Account], query_code: str, max_pages: int) -> dict:
    synced = 0
    errors = []
    for account in accounts:
        if not account.cookie:
            errors.append({"account_id": account.account_id, "error": "Cookie??"})
            continue
        try:
            fetched = await OrderFetcher(account.account_id, account.cookie).fetch_all(query_code=query_code, max_pages=max_pages)
        except Exception as e:
            logger.exception(f"[orders/sync] fetch failed for {account.account_id}")
            errors.append({"account_id": account.account_id, "error": str(e)})
            continue

        if fetched.get("cookies_str") and fetched["cookies_str"] != account.cookie:
            account.cookie = fetched["cookies_str"]
        if not fetched.get("success"):
            if fetched.get("retryable"):
                account.status = "error"
            errors.append({"account_id": account.account_id, "error": fetched.get("error", "????")})
            await db.commit()
            continue

        for data in fetched.get("items", []):
            order_id = data.get("order_id")
            if not order_id:
                continue
            order = (await db.execute(select(Order).where(Order.order_id == order_id))).scalar_one_or_none()
            if not order:
                order = Order(order_id=order_id, account_id=account.account_id)
                db.add(order)
            order.account_id = account.account_id
            order.item_id = data.get("item_id") or order.item_id
            order.buyer_id = data.get("buyer_id") or order.buyer_id
            order.buyer_name = data.get("buyer_name") or order.buyer_name
            order.price = data.get("price") or order.price or 0
            order.status = data.get("status") or order.status or "pending"
            synced += 1
        await db.commit()
    return {"success": True, "synced": synced, "accounts": len(accounts), "errors": errors}


@router.post("/sync")
async def sync_orders(
    account_id: Optional[str] = Query(None),
    query_code: str = Query("ALL"),
    max_pages: int = Query(3, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account_query = select(Account).where(Account.status == "active")
    if account_id:
        account_query = account_query.where(Account.account_id == account_id)
    accounts = (await db.execute(account_query)).scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="没有可同步的账号")
    return await sync_account_orders(db, accounts, query_code, max_pages)


@router.get("")
async def list_orders(
    account_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Order)
    total_query = select(func.count(Order.id))
    if account_id:
        query = query.where(Order.account_id == account_id)
        total_query = total_query.where(Order.account_id == account_id)
    total = (await db.execute(total_query)).scalar() or 0
    result = await db.execute(query.order_by(Order.id.desc()).offset((page - 1) * page_size).limit(page_size))
    orders = result.scalars().all()
    return {"success": True, "data": [OrderResponse.model_validate(order) for order in orders], "total": total, "page": page, "page_size": page_size}
