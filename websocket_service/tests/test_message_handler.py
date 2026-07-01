from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.message_handler import MessageHandler


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
