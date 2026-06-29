from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from ..database import Base

class PublishLog(Base):
    __tablename__ = "publish_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(64), index=True, comment="商品ID")
    account_id = Column(String(80), index=True, comment="账号")
    title = Column(String(200), comment="发布标题")
    status = Column(String(20), default="pending", comment="pending/publishing/published/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    result_item_id = Column(String(64), nullable=True, comment="发布后闲鱼商品ID")
    result_url = Column(String(500), nullable=True, comment="发布后商品链接")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
