from datetime import datetime
from typing import Optional

import aiohttp
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.delivery_config import DeliveryConfig
from ..models.delivery_log import DeliveryLog
from ..models.order import Order


class DeliveryExecutor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _send_text(self, account_id: str, buyer_id: str, content: str, item_id: str = "") -> tuple[bool, str]:
        """通过 websocket 服务发送文本。当前先走统一接口，接口未实现时返回明确错误。"""
        ws_url = "http://websocket:8001"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ws_url}/send/{account_id}",
                json={"buyer_id": buyer_id, "content": content, "msg_type": "text", "item_id": item_id},
                timeout=15,
            ) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {"success": False, "error": await resp.text()}
                if data.get("success"):
                    return True, ""
                return False, data.get("error") or data.get("message") or f"websocket send failed: {resp.status}"

    async def _call_api(self, config: DeliveryConfig, order: Order) -> tuple[bool, str, str]:
        if not config.api_url:
            return False, "", "api_url为空"
        payload = {
            "order_id": order.order_id,
            "account_id": order.account_id,
            "item_id": order.item_id,
            "buyer_id": order.buyer_id,
            "buyer_name": order.buyer_name,
            "price": order.price,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(config.api_url, json=payload, timeout=config.api_timeout or 30) as resp:
                text = await resp.text()
                if resp.status >= 200 and resp.status < 300:
                    return True, text, ""
                return False, text, f"api status {resp.status}: {text[:200]}"

    async def deliver_order(self, order: Order) -> DeliveryLog:
        existing = (await self.db.execute(select(DeliveryLog).where(DeliveryLog.order_id == order.order_id))).scalar_one_or_none()
        if not existing:
            existing = DeliveryLog(
                order_id=order.order_id,
                account_id=order.account_id,
                item_id=order.item_id,
                buyer_id=order.buyer_id,
                status="pending",
            )
            self.db.add(existing)
            await self.db.flush()

        config = (await self.db.execute(
            select(DeliveryConfig).where(
                DeliveryConfig.account_id == order.account_id,
                DeliveryConfig.item_id == order.item_id,
                DeliveryConfig.enabled == True,
            )
        )).scalar_one_or_none()

        if existing.status == "success" and (not config or config.send_once):
            return existing

        existing.attempts = (existing.attempts or 0) + 1
        if not config:
            existing.status = "skipped"
            existing.error = "未配置该商品的发货内容"
            await self.db.commit()
            return existing
        if not order.buyer_id:
            existing.status = "failed"
            existing.error = "订单缺少buyer_id，无法发送消息"
            await self.db.commit()
            return existing

        content = config.delivery_content or ""
        try:
            if config.delivery_type == "api":
                ok, api_content, err = await self._call_api(config, order)
                if ok and api_content:
                    content = api_content
                elif not ok:
                    existing.status = "failed"
                    existing.error = err
                    await self.db.commit()
                    return existing
            if not content.strip():
                existing.status = "failed"
                existing.error = "发货内容为空"
                await self.db.commit()
                return existing
            ok, err = await self._send_text(order.account_id, order.buyer_id, content, order.item_id)
            if ok:
                existing.status = "success"
                existing.content = content
                existing.error = ""
                existing.sent_at = datetime.utcnow()
                order.status = "shipped"
            else:
                existing.status = "failed"
                existing.content = content
                existing.error = err
            await self.db.commit()
            return existing
        except Exception as exc:
            logger.exception(f"deliver order failed: {order.order_id}")
            existing.status = "failed"
            existing.content = content
            existing.error = str(exc)
            await self.db.commit()
            return existing
