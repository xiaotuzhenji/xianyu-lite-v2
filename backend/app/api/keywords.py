from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.keyword_rule import KeywordRule

router = APIRouter(prefix="/keywords", tags=["keywords"])

class KeywordResponse(BaseModel):
    id: int
    account_id: str
    keyword: str
    reply_content: str = ""
    reply_type: str = "text"
    image_url: str = ""
    item_id: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class KeywordCreate(BaseModel):
    account_id: str
    keyword: str
    reply_content: str = ""
    reply_type: str = "text"
    image_url: str = ""
    item_id: Optional[str] = None

@router.get("")
async def list_keywords(
    account_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(KeywordRule)
    if account_id:
        query = query.where(KeywordRule.account_id == account_id)
    if item_id:
        query = query.where(KeywordRule.item_id == item_id)
    query = query.order_by(KeywordRule.id.desc())
    result = await db.execute(query)
    rules = result.scalars().all()
    return {"success": True, "data": [KeywordResponse.model_validate(r) for r in rules]}

@router.post("")
async def create_keyword(data: KeywordCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rule = KeywordRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    return {"success": True}

@router.delete("/{rule_id}")
async def delete_keyword(rule_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await db.execute(delete(KeywordRule).where(KeywordRule.id == rule_id))
    await db.commit()
    return {"success": True}
