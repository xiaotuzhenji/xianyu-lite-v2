import base64
import json
import re
from typing import Any, Callable, Optional

from loguru import logger


PAID_ORDER_KEYWORDS = (
    "[我已付款，等待你发货]",
    "[我已付款，等待您发货]",
    "[已付款，待发货]",
    "我已付款，等待你发货",
    "我已付款，等待您发货",
    "已付款，待发货",
    "买家已付款",
    "等待你发货",
    "等待您发货",
    "待发货",
)

CONFIRM_RECEIPT_KEYWORDS = (
    "[买家确认收货，交易成功]",
    "[你已确认收货，交易成功]",
    "买家已确认收货，交易成功",
    "确认收货",
    "交易成功",
)

ORDER_RELATED_KEYWORDS = (
    "订单",
    "付款",
    "发货",
    "收货",
    "交易",
)


class MessageHandler:
    def __init__(self, cookie_id: str):
        self.cookie_id = cookie_id
        self.on_chat_message: Optional[Callable] = None
        self.on_order_message: Optional[Callable] = None
        self.on_confirm_receipt: Optional[Callable] = None
        self._processed_ids = set()

    def set_chat_handler(self, handler: Callable):
        self.on_chat_message = handler

    def set_order_handler(self, handler: Callable):
        self.on_order_message = handler

    def set_confirm_receipt_handler(self, handler: Callable):
        self.on_confirm_receipt = handler

    async def handle(self, cookie_id: str, data: dict):
        for message in self._iter_messages(data):
            msg_id = self._message_id(message)
            if msg_id and msg_id in self._processed_ids:
                continue
            if msg_id:
                self._processed_ids.add(msg_id)
                if len(self._processed_ids) > 10000:
                    self._processed_ids.clear()

            normalized = self._normalize_message(message)
            if not normalized:
                continue
            msg_type = normalized.get("type")
            if msg_type == "chat_message" and self.on_chat_message:
                await self.on_chat_message(cookie_id, normalized)
            elif msg_type == "order_update" and self.on_order_message:
                await self.on_order_message(cookie_id, normalized)
            elif msg_type == "confirm_receipt" and self.on_confirm_receipt:
                await self.on_confirm_receipt(cookie_id, normalized)

    def _iter_messages(self, data: dict) -> list[dict]:
        if self._is_sync_package(data):
            messages = []
            for item in data.get("body", {}).get("syncPushPackage", {}).get("data", []) or []:
                decoded = self._decode_sync_item(item)
                if isinstance(decoded, dict):
                    messages.append(decoded)
            return messages
        return [data] if isinstance(data, dict) else []

    @staticmethod
    def _is_sync_package(data: dict) -> bool:
        return isinstance(data, dict) and isinstance(data.get("body"), dict) and isinstance(
            data["body"].get("syncPushPackage"), dict
        )

    def _decode_sync_item(self, item: dict) -> Optional[dict]:
        raw = item.get("data") if isinstance(item, dict) else None
        if not raw:
            return None
        try:
            text = base64.b64decode(raw).decode("utf-8")
            return json.loads(text)
        except Exception:
            logger.debug(f"[{self.cookie_id}] unsupported encrypted sync message")
            return None

    def _message_id(self, message: dict) -> str:
        for candidate in (
            message.get("id"),
            message.get("messageId"),
            self._json_get(message.get("bizTag"), "messageId"),
            self._json_get(message.get("extJson"), "messageId"),
        ):
            if candidate:
                return str(candidate)
        message_1 = message.get("1") if isinstance(message.get("1"), dict) else {}
        message_10 = message_1.get("10") if isinstance(message_1.get("10"), dict) else {}
        for source in (message_10.get("bizTag"), message_10.get("extJson")):
            candidate = self._json_get(source, "messageId")
            if candidate:
                return str(candidate)
        return ""

    def _normalize_message(self, message: dict) -> Optional[dict]:
        direct_type = message.get("type")
        if direct_type in {"chat_message", "order_update", "confirm_receipt"}:
            return message

        parsed = self._parse_goofish_message(message)
        if not parsed:
            return None

        content = parsed.get("content", "")
        if self._is_confirm_receipt_content(content):
            parsed["type"] = "confirm_receipt"
            return parsed
        if self._is_paid_order_content(content) or self._looks_like_order_update(parsed):
            parsed["type"] = "order_update"
            parsed["status"] = parsed.get("status") or "paid"
            return parsed
        parsed["type"] = "chat_message"
        return parsed

    def _parse_goofish_message(self, message: dict) -> Optional[dict]:
        if isinstance(message.get("1"), dict):
            message_1 = message.get("1") or {}
            message_10 = message_1.get("10") if isinstance(message_1.get("10"), dict) else {}
            message_1_1 = message_1.get("1") if isinstance(message_1.get("1"), dict) else {}
            chat_id = self._strip_goofish(message_1.get("2", ""))
            content = str(message_10.get("reminderContent") or message.get("content") or "")
            buyer_id = str(message_10.get("senderUserId") or self._strip_goofish(message_1_1.get("1", "")) or "")
            buyer_name = str(message_10.get("senderNick") or message_10.get("reminderTitle") or "")
            item_id = self._extract_item_id(message_10) or self._extract_item_id(message_1)
            order_id = self._extract_order_id(message_10) or self._extract_order_id(message_1) or self._extract_order_id(message)
        elif isinstance(message.get("4"), dict):
            message_4 = message.get("4") or {}
            chat_id = self._strip_goofish(message.get("2", ""))
            content = str(message_4.get("reminderContent") or "")
            buyer_id = str(message_4.get("senderUserId") or "")
            buyer_name = str(message_4.get("senderNick") or message_4.get("reminderTitle") or "")
            item_id = self._extract_item_id(message_4) or self._extract_item_id(message)
            order_id = self._extract_order_id(message_4) or self._extract_order_id(message)
        else:
            return None

        if not content and not order_id:
            return None
        return {
            "content": content,
            "text": content,
            "chat_id": chat_id or buyer_id,
            "conversation_id": chat_id or buyer_id,
            "buyer_id": buyer_id,
            "sender_id": buyer_id,
            "buyer_name": buyer_name,
            "item_id": item_id,
            "order_id": order_id,
            "raw": message,
        }

    @staticmethod
    def _strip_goofish(value: Any) -> str:
        text = str(value or "")
        return text.split("@", 1)[0] if "@" in text else text

    @staticmethod
    def _json_get(value: Any, key: str) -> Any:
        if isinstance(value, dict):
            return value.get(key)
        if isinstance(value, str) and value:
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed.get(key)
            except Exception:
                return None
        return None

    def _extract_item_id(self, source: Any) -> str:
        text = self._deep_text(source)
        for pattern in (r"(?:itemId|item_id)[^0-9]{0,20}(\d{6,})", r'"itemId"\s*:\s*"?(\d+)"?'):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _extract_order_id(self, source: Any) -> str:
        text = self._deep_text(source)
        for pattern in (
            r"(?:orderId|tradeId|order_id|trade_id)[^0-9]{0,20}(\d{6,})",
            r'"orderId"\s*:\s*"?(\d+)"?',
            r'"tradeId"\s*:\s*"?(\d+)"?',
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _deep_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    @staticmethod
    def _is_paid_order_content(content: str) -> bool:
        return any(keyword in (content or "") for keyword in PAID_ORDER_KEYWORDS)

    @staticmethod
    def _is_confirm_receipt_content(content: str) -> bool:
        return any(keyword in (content or "") for keyword in CONFIRM_RECEIPT_KEYWORDS)

    @staticmethod
    def _looks_like_order_update(message: dict) -> bool:
        content = str(message.get("content") or "")
        order_id = str(message.get("order_id") or "")
        item_id = str(message.get("item_id") or "")
        buyer_id = str(message.get("buyer_id") or "")
        if not order_id:
            return False
        if any(keyword in content for keyword in ORDER_RELATED_KEYWORDS):
            return True
        return bool(item_id and buyer_id)
