from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from ..database import Base

class DefaultReply(Base):
    __tablename__ = "default_replies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), index=True, nullable=False)
    item_id = Column(String(64), nullable=True, comment="商品ID,空=账号级")
    enabled = Column(Boolean, default=False)
    reply_type = Column(String(16), default="text", comment="text/api")
    reply_content = Column(Text)
    reply_image = Column(String(500))
    api_url = Column(String(1024))
    api_timeout = Column(Integer, default=80)
    reply_once = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
