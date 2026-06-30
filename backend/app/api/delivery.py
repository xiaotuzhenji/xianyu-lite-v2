from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.delivery_config import DeliveryConfig
from ..models.delivery_log import DeliveryLog
from ..models.item import Item
from ..models.user import User

router = APIRouter(prefix="/delivery", tags=["delivery"])

class DeliveryConfigRequest(BaseModel):
    item_id: str
    enabled: bool = True
    delivery_type: str = "text"
    delivery_content: str = ""
    api_url: str = ""
    api_timeout: int = 30
    send_once: bool = True

class DeliveryConfigResponse(BaseModel):
    id: int
    account_id: str
    item_id: str
    enabled: bool = True
    delivery_type: str = "text"
    delivery_content: str = ""
    api_url: str = ""
    api_timeout: int = 30
    send_once: bool = True

    class Config:
        from_attributes = True

class DeliveryLogResponse(BaseModel):
    id: int
    order_id: str
    account_id: str
    item_id: str = ""
    buyer_id: str = ""
    status: str
    content: str = ""
    error: str = ""
    attempts: int = 0
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


async def _get_owned_account(db: AsyncSession, account_id: str, user: User) -> Optional[Account]:
    stmt = select(Account).where(Account.account_id == account_id, Account.owner_id == user.id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_owned_item(db: AsyncSession, account_id: str, item_id: str, user: User) -> Optional[Item]:
    stmt = (
        select(Item)
        .join(Account, Item.account_id == Account.account_id)
        .where(Item.account_id == account_id, Item.item_id == item_id, Account.owner_id == user.id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("/configs/{account_id}")
async def list_configs(account_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not await _get_owned_account(db, account_id, user):
        raise HTTPException(status_code=404, detail="账号不存在或无权限")
    result = await db.execute(select(DeliveryConfig).where(DeliveryConfig.account_id == account_id).order_by(DeliveryConfig.id.desc()))
    configs = result.scalars().all()
    return {"success": True, "data": [DeliveryConfigResponse.model_validate(c) for c in configs]}

@router.get("/configs/{account_id}/{item_id}")
async def get_config(account_id: str, item_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not await _get_owned_item(db, account_id, item_id, user):
        raise HTTPException(status_code=404, detail="商品不存在或无权限")
    result = await db.execute(select(DeliveryConfig).where(DeliveryConfig.account_id == account_id, DeliveryConfig.item_id == item_id))
    config = result.scalar_one_or_none()
    if not config:
        return {"success": True, "data": None}
    return {"success": True, "data": DeliveryConfigResponse.model_validate(config)}

@router.put("/configs/{account_id}")
async def upsert_config(account_id: str, data: DeliveryConfigRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not data.item_id:
        raise HTTPException(status_code=400, detail="item_id不能为空")
    if data.enabled:
        if data.delivery_type == "api":
            if not data.api_url.strip():
                raise HTTPException(status_code=400, detail="启用 API 发货时必须填写接口地址")
        elif not data.delivery_content.strip():
            raise HTTPException(status_code=400, detail="启用自动发货时必须填写发货内容")
    if not await _get_owned_item(db, account_id, data.item_id, user):
        raise HTTPException(status_code=404, detail="商品不存在或无权限")
    result = await db.execute(select(DeliveryConfig).where(DeliveryConfig.account_id == account_id, DeliveryConfig.item_id == data.item_id))
    config = result.scalar_one_or_none()
    if not config:
        config = DeliveryConfig(account_id=account_id, item_id=data.item_id)
        db.add(config)
    config.enabled = data.enabled
    config.delivery_type = data.delivery_type
    config.delivery_content = data.delivery_content
    config.api_url = data.api_url
    config.api_timeout = data.api_timeout
    config.send_once = data.send_once
    await db.commit()
    return {"success": True}

@router.delete("/configs/{account_id}/{item_id}")
async def delete_config(account_id: str, item_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not await _get_owned_item(db, account_id, item_id, user):
        raise HTTPException(status_code=404, detail="商品不存在或无权限")
    result = await db.execute(select(DeliveryConfig).where(DeliveryConfig.account_id == account_id, DeliveryConfig.item_id == item_id))
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)
        await db.commit()
    return {"success": True}

@router.get("/logs")
async def list_logs(
    account_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned_accounts = select(Account.account_id).where(Account.owner_id == user.id)
    query = select(DeliveryLog).where(DeliveryLog.account_id.in_(owned_accounts))
    count_query = select(func.count(DeliveryLog.id)).where(DeliveryLog.account_id.in_(owned_accounts))
    if account_id:
        query = query.where(DeliveryLog.account_id == account_id)
        count_query = count_query.where(DeliveryLog.account_id == account_id)
    if item_id:
        query = query.where(DeliveryLog.item_id == item_id)
        count_query = count_query.where(DeliveryLog.item_id == item_id)
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.order_by(DeliveryLog.id.desc()).offset((page - 1) * page_size).limit(page_size))
    logs = result.scalars().all()
    return {"success": True, "data": [DeliveryLogResponse.model_validate(l) for l in logs], "total": total, "page": page, "page_size": page_size}


@router.post("/orders/{order_id}/deliver")
async def deliver_order_endpoint(order_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models.order import Order
    from ..services.delivery import DeliveryExecutor
    result = await db.execute(
        select(Order)
        .join(Account, Order.account_id == Account.account_id)
        .where(Order.order_id == order_id, Account.owner_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    log = await DeliveryExecutor(db).deliver_order(order)
    return {"success": log.status == "success", "data": DeliveryLogResponse.model_validate(log)}
