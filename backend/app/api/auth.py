from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.auth import authenticate_user, create_access_token, decode_access_token
from ..deps import get_current_user
from ..models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str = ""
    username: str = ""
    is_admin: bool = False
    message: str = ""


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": str(user.id), "username": user.username, "is_admin": user.is_admin})
    return LoginResponse(success=True, token=token, username=user.username, is_admin=user.is_admin)


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"success": True, "username": user.username, "is_admin": user.is_admin}
