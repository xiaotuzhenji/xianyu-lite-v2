from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.default_reply import DefaultReply

router = APIRouter(prefix="/default-replies", tags=["default-replies"])

class DefaultReplyResponse(BaseModel):
    enabled: bool = False
    reply_type: str = "text"
    reply_content: str = ""
    reply_image: str = ""
    api_url: str = ""
    api_timeout: int = 80
    reply_once: bool = False

class DefaultReplyUpdate(BaseModel):
    enabled: bool = False
    reply_content: str = ""
    reply_image: str = ""
    reply_type: str = "text"
    api_url: str = ""
    api_timeout: int = 80
    reply_once: bool = False

@router.get("/{account_id}")
async def get_default_reply(
    account_id: str, item_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    if item_id:
        result = await db.execute(
            select(DefaultReply).where(DefaultReply.account_id == account_id, DefaultReply.item_id == item_id)
        )
        reply = result.scalar_one_or_none()
        if reply:
            return DefaultReplyResponse(**{"enabled": reply.enabled, "reply_type": reply.reply_type or "text", "reply_content": reply.reply_content or "", "reply_image": reply.reply_image or "", "api_url": reply.api_url or "", "api_timeout": reply.api_timeout or 80, "reply_once": reply.reply_once})
    result = await db.execute(
        select(DefaultReply).where(DefaultReply.account_id == account_id, DefaultReply.item_id.is_(None))
    )
    reply = result.scalar_one_or_none()
    if not reply:
        return DefaultReplyResponse()
    return DefaultReplyResponse(**{"enabled": reply.enabled, "reply_type": reply.reply_type or "text", "reply_content": reply.reply_content or "", "reply_image": reply.reply_image or "", "api_url": reply.api_url or "", "api_timeout": reply.api_timeout or 80, "reply_once": reply.reply_once})

@router.put("/{account_id}")
async def update_default_reply(
    account_id: str, data: DefaultReplyUpdate, item_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    query = select(DefaultReply).where(DefaultReply.account_id == account_id)
    if item_id:
        query = query.where(DefaultReply.item_id == item_id)
    else:
        query = query.where(DefaultReply.item_id.is_(None))
    result = await db.execute(query)
    reply = result.scalar_one_or_none()
    if reply:
        reply.enabled = data.enabled
        reply.reply_content = data.reply_content
        reply.reply_image = data.reply_image
        reply.reply_type = data.reply_type
        reply.api_url = data.api_url
        reply.api_timeout = data.api_timeout
        reply.reply_once = data.reply_once
    else:
        reply = DefaultReply(account_id=account_id, item_id=item_id, **data.model_dump())
        db.add(reply)
    await db.commit()
    return {"success": True}
