from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func
from ..database import Base

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), unique=True, nullable=False, index=True, comment="闲鱼账号标识")
    remark = Column(String(200), comment="备注名称")
    cookie = Column(Text, comment="Cookie字符串")
    status = Column(String(20), default="active", comment="active/disabled/error")
    owner_id = Column(Integer, index=True, comment="所属用户ID")
    auto_confirm = Column(Boolean, default=True, comment="自动确认发货")
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
