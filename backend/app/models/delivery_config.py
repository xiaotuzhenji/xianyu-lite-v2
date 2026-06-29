from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, UniqueConstraint, func
from ..database import Base

class DeliveryConfig(Base):
    __tablename__ = "delivery_configs"
    __table_args__ = (UniqueConstraint("account_id", "item_id", name="uq_delivery_account_item"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), index=True, nullable=False)
    item_id = Column(String(64), index=True, nullable=False)
    enabled = Column(Boolean, default=True)
    delivery_type = Column(String(20), default="text", comment="text/card/api")
    delivery_content = Column(Text, comment="发货文本或卡密内容")
    api_url = Column(String(500), comment="外部发货接口")
    api_timeout = Column(Integer, default=30)
    send_once = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
