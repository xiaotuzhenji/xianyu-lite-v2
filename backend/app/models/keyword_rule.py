from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from ..database import Base

class KeywordRule(Base):
    __tablename__ = "keyword_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), index=True, nullable=False, comment="账号ID")
    keyword = Column(String(200), nullable=False, comment="关键词(多行)")
    reply_content = Column(Text, comment="回复内容")
    reply_type = Column(String(16), default="text", comment="text/image")
    image_url = Column(String(500), comment="图片URL")
    item_id = Column(String(64), nullable=True, index=True, comment="绑定商品ID,空=通用")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
