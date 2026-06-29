from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.confirm_receipt import ConfirmReceiptConfig

router = APIRouter(prefix="/confirm-receipt", tags=["confirm-receipt"])

class ConfigResponse(BaseModel):
    enabled: bool = False
    message_content: str = ""
    message_image: str = ""
    reply_once: bool = True
    item_id: Optional[str] = None

class ConfigUpdate(BaseModel):
    enabled: bool = False
    message_content: str = ""
    message_image: str = ""
    reply_once: bool = True
    item_id: Optional[str] = None

@router.get("/{account_id}")
async def get_config(
    account_id: str,
    item_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 优先查商品级
    if item_id:
        result = await db.execute(
            select(ConfirmReceiptConfig).where(
                ConfirmReceiptConfig.account_id == account_id,
                ConfirmReceiptConfig.item_id == item_id,
            )
        )
        config = result.scalar_one_or_none()
        if config:
            return ConfigResponse(enabled=config.enabled, message_content=config.message_content or "", message_image=config.message_image or "", reply_once=config.reply_once, item_id=config.item_id)
    # 退回到账号级
    result = await db.execute(
        select(ConfirmReceiptConfig).where(
            ConfirmReceiptConfig.account_id == account_id,
            ConfirmReceiptConfig.item_id.is_(None),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        return ConfigResponse()
    return ConfigResponse(enabled=config.enabled, message_content=config.message_content or "", message_image=config.message_image or "", reply_once=config.reply_once, item_id=None)

@router.put("/{account_id}")
async def update_config(
    account_id: str,
    data: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ConfirmReceiptConfig).where(ConfirmReceiptConfig.account_id == account_id)
    if data.item_id:
        query = query.where(ConfirmReceiptConfig.item_id == data.item_id)
    else:
        query = query.where(ConfirmReceiptConfig.item_id.is_(None))
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    if config:
        config.enabled = data.enabled
        config.message_content = data.message_content
        config.message_image = data.message_image
        config.reply_once = data.reply_once
    else:
        config = ConfirmReceiptConfig(
            account_id=account_id,
            item_id=data.item_id,
            enabled=data.enabled,
            message_content=data.message_content,
            message_image=data.message_image,
            reply_once=data.reply_once,
        )
        db.add(config)
    await db.commit()
    return {"success": True}
