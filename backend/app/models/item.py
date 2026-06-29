from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, func
from sqlalchemy import Boolean
from ..database import Base

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(64), unique=True, nullable=False, index=True, comment="闲鱼商品ID")
    account_id = Column(String(80), index=True, comment="所属账号")
    title = Column(String(200), comment="商品标题")
    price = Column(Float, default=0)
    description = Column(Text, comment="商品描述")
    image_urls = Column(Text, comment="图片URLs(JSON)")
    status = Column(String(20), default="online", comment="online/offline")
    publish_status = Column(String(20), default="draft", comment="draft/publishing/published/failed")
    publish_error = Column(Text, nullable=True, comment="发布失败原因")
    url = Column(String(500), comment="商品链接")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
