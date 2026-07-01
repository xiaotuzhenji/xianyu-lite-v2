from pathlib import Path
import sys
import asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.message_handler import MessageHandler
from app.main import _build_order_payload


def _build_standard_message(content: str, item_id: str = "1234567890", order_id: str = "9876543210", buyer_id: str = "buyer001"):
    return {
        "1": {
            "1": {"1": f"{buyer_id}@goofish"},
            "2": f"{buyer_id}@goofish",
            "10": {
                "reminderContent": content,
                "senderUserId": buyer_id,
                "senderNick": "买家A",
                "itemId": item_id,
                "orderId": order_id,
            },
        }
    }


def test_paid_order_message_is_detected():
    handler = MessageHandler("acc1")
    normalized = handler._normalize_message(_build_standard_message("[我已付款，等待你发货]"))
    assert normalized is not None
    assert normalized["type"] == "order_update"
    assert normalized["status"] == "paid"
    assert normalized["item_id"] == "1234567890"
    assert normalized["order_id"] == "9876543210"


def test_confirm_receipt_message_is_detected():
    handler = MessageHandler("acc1")
    normalized = handler._normalize_message(_build_standard_message("买家已确认收货，交易成功"))
    assert normalized is not None
    assert normalized["type"] == "confirm_receipt"


def test_order_message_fallback_by_ids():
    handler = MessageHandler("acc1")
    normalized = handler._normalize_message(_build_standard_message("订单提醒"))
    assert normalized is not None
    assert normalized["type"] == "order_update"


def test_paid_order_without_order_id_is_dispatched_with_message_id():
    handler = MessageHandler("acc1")
    captured = []

    async def on_order(cookie_id: str, data: dict):
        captured.append((cookie_id, data))

    handler.set_order_handler(on_order)
    message = _build_standard_message("[我已付款，等待你发货]", order_id="")
    message["messageId"] = "msg-1001"
    asyncio.run(handler.handle("acc1", message))

    assert len(captured) == 1
    assert captured[0][0] == "acc1"
    assert captured[0][1]["message_id"] == "msg-1001"
    assert captured[0][1]["order_id"] == ""


def test_paid_order_without_message_id_uses_hash_key_once():
    handler = MessageHandler("acc1")
    captured = []

    async def on_order(cookie_id: str, data: dict):
        captured.append((cookie_id, data))

    handler.set_order_handler(on_order)
    message = _build_standard_message("[我已付款，等待你发货]", order_id="")
    asyncio.run(handler.handle("acc1", message))
    asyncio.run(handler.handle("acc1", message))

    assert len(captured) == 1
    assert len(captured[0][1]["message_id"]) == 40
    assert captured[0][1]["order_id"] == ""


def test_paid_card_update_without_order_id_is_detected():
    handler = MessageHandler("acc1")
    normalized = handler._normalize_message({
        "1": "item:1234567890",
        "2": "buyer001@goofish",
        "4": {
            "reminderContent": "[已付款，待发货]",
            "senderUserId": "buyer001",
            "reminderTitle": "买家A",
            "reminderUrl": "https://www.goofish.com/item?id=1234567890&itemId=1234567890",
        },
    })

    assert normalized is not None
    assert normalized["type"] == "order_update"
    assert normalized["status"] == "paid"
    assert normalized["item_id"] == "1234567890"
    assert normalized["buyer_id"] == "buyer001"
    assert normalized["order_id"] == ""


def test_confirm_receipt_is_not_treated_as_paid_order():
    handler = MessageHandler("acc1")
    normalized = handler._normalize_message(_build_standard_message("确认收货，交易成功"))

    assert normalized is not None
    assert normalized["type"] == "confirm_receipt"


def test_order_payload_uses_stable_fallback_order_id():
    data = {
        "message_id": "msg-1001",
        "item_id": "1234567890",
        "buyer_id": "buyer001",
        "status": "paid",
    }
    payload = _build_order_payload("acc1", data)

    assert payload["order_id"].startswith("ws-")
    assert len(payload["order_id"]) <= 64
    assert payload == _build_order_payload("acc1", data)


if __name__ == "__main__":
    test_paid_order_message_is_detected()
    test_confirm_receipt_message_is_detected()
    test_order_message_fallback_by_ids()
    test_paid_order_without_order_id_is_dispatched_with_message_id()
    test_paid_order_without_message_id_uses_hash_key_once()
    test_paid_card_update_without_order_id_is_detected()
    test_confirm_receipt_is_not_treated_as_paid_order()
    test_order_payload_uses_stable_fallback_order_id()
