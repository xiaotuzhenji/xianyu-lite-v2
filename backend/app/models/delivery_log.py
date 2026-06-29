from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, UniqueConstraint, func
from ..database import Base

class DeliveryLog(Base):
    __tablename__ = "delivery_logs"
    __table_args__ = (UniqueConstraint("order_id", name="uq_delivery_order"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), index=True, nullable=False)
    account_id = Column(String(80), index=True, nullable=False)
    item_id = Column(String(64), index=True)
    buyer_id = Column(String(64), index=True)
    status = Column(String(20), default="pending", comment="pending/success/failed/skipped")
    content = Column(Text)
    error = Column(Text)
    attempts = Column(Integer, default=0)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
