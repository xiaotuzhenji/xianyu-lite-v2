from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func, UniqueConstraint
from ..database import Base

class ConfirmReceiptConfig(Base):
    __tablename__ = "confirm_receipt_configs"
    __table_args__ = (UniqueConstraint("account_id", "item_id", name="uk_account_item"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), nullable=False, index=True)
    item_id = Column(String(64), nullable=True, comment="商品ID,空=账号级配置")
    enabled = Column(Boolean, default=False)
    message_content = Column(Text, comment="发送的消息文本")
    message_image = Column(String(500), comment="消息图片URL")
    reply_once = Column(Boolean, default=True, comment="对同一用户只发送一次")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
