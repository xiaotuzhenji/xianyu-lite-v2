from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func, UniqueConstraint
from ..database import Base

class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("account_id", "stat_date", name="uk_account_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), index=True, nullable=False)
    stat_date = Column(Date, nullable=False)
    msg_received = Column(Integer, default=0, comment="收到消息数")
    msg_replied = Column(Integer, default=0, comment="自动回复数")
    orders_count = Column(Integer, default=0, comment="订单数")
    orders_amount = Column(Float, default=0, comment="订单金额")
    confirm_sent = Column(Integer, default=0, comment="确认收货消息数")
    created_at = Column(DateTime, server_default=func.now())
