from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.account import Account

router = APIRouter(prefix="/accounts", tags=["accounts"])

class AccountResponse(BaseModel):
    id: int
    account_id: str
    remark: str = ""
    status: str = "active"
    auto_confirm: bool = True
    last_active_at: Optional[datetime] = None
    keyword_count: int = 0

    class Config:
        from_attributes = True

class AccountUpdate(BaseModel):
    remark: Optional[str] = None
    status: Optional[str] = None
    auto_confirm: Optional[bool] = None
    cookie: Optional[str] = None


async def _get_owned_account(db: AsyncSession, account_id: str, user: User) -> Optional[Account]:
    result = await db.execute(
        select(Account).where(Account.account_id == account_id, Account.owner_id == user.id)
    )
    return result.scalar_one_or_none()

@router.get("")
async def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total_q = select(func.count(Account.id)).where(Account.owner_id == user.id)
    total_r = await db.execute(total_q)
    total = total_r.scalar()

    query = (
        select(Account)
        .where(Account.owner_id == user.id)
        .order_by(Account.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    accounts = result.scalars().all()

    return {
        "success": True,
        "data": [AccountResponse.model_validate(a) for a in accounts],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/{account_id}")
async def get_account(account_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    account = await _get_owned_account(db, account_id, user)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"success": True, "data": AccountResponse.model_validate(account)}

@router.put("/{account_id}")
async def update_account(account_id: str, data: AccountUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    account = await _get_owned_account(db, account_id, user)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if data.remark is not None:
        account.remark = data.remark
    if data.status is not None:
        account.status = data.status
    if data.auto_confirm is not None:
        account.auto_confirm = data.auto_confirm
    if data.cookie is not None:
        account.cookie = data.cookie
    await db.commit()
    return {"success": True}

@router.post("")
async def create_account(data: AccountUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not data.cookie:
        raise HTTPException(status_code=400, detail="Cookie不能为空")
    import uuid, re
    # 自动从cookie中提取unb作为account_id, 没有则生成随机ID
    match = re.search(r"unb[=\s]+([^;\s]+)", data.cookie)
    account_id = match.group(1) if match else "acc_" + uuid.uuid4().hex[:8]
    # 检查是否已存在
    result = await db.execute(select(Account).where(Account.account_id == account_id))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.owner_id != user.id:
            raise HTTPException(status_code=409, detail="账号已被其他用户绑定")
        # 更新cookie
        existing.cookie = data.cookie
        existing.remark = data.remark or existing.remark
        await db.commit()
        return {"success": True, "account_id": account_id, "updated": True}
    account = Account(account_id=account_id, cookie=data.cookie, remark=data.remark or "", owner_id=user.id)
    db.add(account)
    await db.commit()
    return {"success": True, "account_id": account_id, "updated": False}

@router.delete("/{account_id}")
async def delete_account(account_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    account = await _get_owned_account(db, account_id, user)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return {"success": True}
