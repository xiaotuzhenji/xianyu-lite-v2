import os

import aiohttp
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.delivery_config import DeliveryConfig
from ..models.delivery_log import DeliveryLog
from ..models.item import Item
from ..models.order import Order
from ..models.user import User

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


async def _websocket_status() -> dict:
    ws_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://websocket:8001")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ws_url}/status", timeout=5) as resp:
                return await resp.json()
    except Exception as exc:
        return {"success": False, "error": str(exc), "active": [], "configured": []}


@router.get("/production")
async def production_diagnostics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ws = await _websocket_status()
    active_ws = set(str(item) for item in ws.get("active", []))

    accounts = (await db.execute(select(Account).where(Account.status == "active"))).scalars().all()
    total_items = (await db.execute(select(func.count(Item.id)))).scalar() or 0
    enabled_configs = (await db.execute(select(func.count(DeliveryConfig.id)).where(DeliveryConfig.enabled == True))).scalar() or 0
    pending_orders = (await db.execute(select(func.count(Order.id)).where(Order.status.in_(["paid", "pending"])))).scalar() or 0
    failed_logs = (await db.execute(select(func.count(DeliveryLog.id)).where(DeliveryLog.status == "failed"))).scalar() or 0
    skipped_logs = (await db.execute(select(func.count(DeliveryLog.id)).where(DeliveryLog.status == "skipped"))).scalar() or 0
    items = (await db.execute(select(Item).order_by(Item.id.desc()).limit(200))).scalars().all()
    enabled_config_rows = (
        await db.execute(select(DeliveryConfig.account_id, DeliveryConfig.item_id).where(DeliveryConfig.enabled == True))
    ).all()
    enabled_config_keys = {(row[0], row[1]) for row in enabled_config_rows}
    enabled_config_objects = (
        await db.execute(select(DeliveryConfig).where(DeliveryConfig.enabled == True).limit(200))
    ).scalars().all()
    invalid_delivery_configs = [
        {
            "account_id": config.account_id,
            "item_id": config.item_id,
            "delivery_type": config.delivery_type,
            "reason": "API 发货缺少接口地址" if config.delivery_type == "api" else "发货内容为空",
        }
        for config in enabled_config_objects
        if (
            (config.delivery_type == "api" and not (config.api_url or "").strip())
            or (config.delivery_type != "api" and not (config.delivery_content or "").strip())
        )
    ]
    items_missing_delivery = [
        {
            "account_id": item.account_id,
            "item_id": item.item_id,
            "title": item.title,
            "status": item.status,
        }
        for item in items
        if (item.account_id, item.item_id) not in enabled_config_keys
    ]

    account_rows = []
    for account in accounts:
        item_count = (await db.execute(select(func.count(Item.id)).where(Item.account_id == account.account_id))).scalar() or 0
        config_count = (
            await db.execute(
                select(func.count(DeliveryConfig.id)).where(
                    DeliveryConfig.account_id == account.account_id,
                    DeliveryConfig.enabled == True,
                )
            )
        ).scalar() or 0
        account_rows.append({
            "account_id": account.account_id,
            "has_cookie": bool(account.cookie),
            "websocket_online": account.account_id in active_ws,
            "items": item_count,
            "enabled_delivery_configs": config_count,
        })

    issues = []
    if not accounts:
        issues.append("没有 active 账号")
    if any(not row["has_cookie"] for row in account_rows):
        issues.append("存在未配置 Cookie 的账号")
    if any(not row["websocket_online"] for row in account_rows):
        issues.append("存在 WebSocket 未在线账号")
    if total_items == 0:
        issues.append("没有已同步商品")
    if enabled_configs == 0:
        issues.append("没有开启任何商品级发货配置")
    elif items_missing_delivery:
        issues.append("存在未开启发货配置的商品")
    if invalid_delivery_configs:
        issues.append("存在已开启但无效的发货配置")
    if failed_logs:
        issues.append("存在失败发货日志")
    if skipped_logs:
        issues.append("存在跳过发货日志")

    return {
        "success": True,
        "ready": len(issues) == 0,
        "issues": issues,
        "websocket": ws,
        "summary": {
            "active_accounts": len(accounts),
            "items": total_items,
            "enabled_delivery_configs": enabled_configs,
            "items_missing_delivery_configs": len(items_missing_delivery),
            "invalid_delivery_configs": len(invalid_delivery_configs),
            "pending_orders": pending_orders,
            "failed_delivery_logs": failed_logs,
            "skipped_delivery_logs": skipped_logs,
        },
        "accounts": account_rows,
        "items_missing_delivery_configs": items_missing_delivery[:20],
        "invalid_delivery_configs": invalid_delivery_configs[:20],
    }
