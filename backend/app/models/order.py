from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, func
from ..database import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, nullable=False, index=True)
    account_id = Column(String(80), index=True, nullable=False)
    item_id = Column(String(64), index=True)
    buyer_id = Column(String(64), index=True)
    buyer_name = Column(String(100))
    price = Column(Float, default=0)
    status = Column(String(20), default="pending", comment="pending/paid/shipped/received/rated/closed")
    is_rated = Column(Boolean, default=False, comment="是否已评价")
    confirm_receipt_sent = Column(Boolean, default=False, comment="确认收货消息已发送")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
