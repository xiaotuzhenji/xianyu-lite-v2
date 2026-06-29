from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date, timedelta

from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.statistics import DailyStat
from ..models.account import Account
from ..models.order import Order
from ..models.item import Item

router = APIRouter(prefix="/statistics", tags=["statistics"])

@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 账号总数
    acc_r = await db.execute(select(func.count(Account.id)))
    total_accounts = acc_r.scalar()

    # 商品总数
    item_r = await db.execute(select(func.count(Item.id)))
    total_items = item_r.scalar()

    # 订单总数
    order_r = await db.execute(select(func.count(Order.id)))
    total_orders = order_r.scalar()

    # 今日订单
    today = date.today()
    today_r = await db.execute(
        select(func.count(Order.id)).where(func.date(Order.created_at) == today)
    )
    today_orders = today_r.scalar()

    # 近7天统计数据
    seven_days_ago = today - timedelta(days=7)
    stats_r = await db.execute(
        select(func.sum(DailyStat.msg_received), func.sum(DailyStat.msg_replied), func.sum(DailyStat.orders_amount))
        .where(DailyStat.stat_date >= seven_days_ago)
    )
    row = stats_r.first()
    total_received = row[0] or 0
    total_replied = row[1] or 0
    total_amount = float(row[2] or 0)

    return {
        "success": True,
        "data": {
            "total_accounts": total_accounts,
            "total_items": total_items,
            "total_orders": total_orders,
            "today_orders": today_orders,
            "week_msg_received": total_received,
            "week_msg_replied": total_replied,
            "week_order_amount": total_amount,
        },
    }

@router.get("/daily")
async def get_daily_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    start = today - timedelta(days=days - 1)
    result = await db.execute(
        select(DailyStat).where(DailyStat.stat_date >= start).order_by(DailyStat.stat_date)
    )
    stats = result.scalars().all()
    return {"success": True, "data": [{"stat_date": str(s.stat_date), "msg_received": s.msg_received, "msg_replied": s.msg_replied, "orders_count": s.orders_count, "orders_amount": s.orders_amount} for s in stats]}
