"""二维码扫码登录API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.account import Account
from ..services.qr_login import qr_login_manager
import asyncio

router = APIRouter(prefix="/qr-login", tags=["qr-login"])

# 存储每个会话对应的用户
session_owners: dict = {}


@router.post("/generate")
async def generate_qr_code(user: User = Depends(get_current_user)):
    """生成登录二维码"""
    result = await qr_login_manager.generate_qr_code()
    if result.get("success"):
        session_id = result["session_id"]
        session_owners[session_id] = user.id
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "qr_code_url": result["qr_code_url"],
            }
        }
    return {"success": False, "message": result.get("message", "生成失败")}


@router.get("/status/{session_id}")
async def get_qr_status(session_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """查询扫码状态"""
    session = qr_login_manager.sessions.get(session_id)
    if not session:
        return {"success": False, "data": {"status": "not_found"}}
    
    status_info = qr_login_manager.get_session_status(session_id)
    
    # 如果扫码成功, 自动创建或更新账号
    if status_info.get("status") == "success":
        cookies_str = status_info.get("cookies", "")
        unb = status_info.get("unb", "")
        
        if unb and cookies_str:
            result = await db.execute(select(Account).where(Account.account_id == unb))
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.cookie = cookies_str
                existing.status = "active"
                await db.commit()
                return {"success": True, "data": {"status": "success", "account_id": unb, "is_new": False}}
            else:
                import uuid
                account = Account(
                    account_id=unb,
                    cookie=cookies_str,
                    remark=f"扫码_{unb[-4:]}",
                    owner_id=user.id,
                    status="active",
                )
                db.add(account)
                await db.commit()
                return {"success": True, "data": {"status": "success", "account_id": unb, "is_new": True}}
    
    return {"success": True, "data": status_info}


@router.post("/poll/{session_id}")
async def start_poll(session_id: str, user: User = Depends(get_current_user)):
    """开始轮询二维码状态(异步)"""
    asyncio.create_task(qr_login_manager._monitor_qr_status(session_id))
    return {"success": True, "message": "轮询已开始"}
