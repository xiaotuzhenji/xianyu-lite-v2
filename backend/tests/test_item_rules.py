from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.api.items import ItemCreateRequest, ItemUpdateRequest, _can_delete_item, _image_count, _is_item_account_conflict, _new_draft_item_id, _normalize_image_urls, _parse_image_urls, _uploaded_image_paths, _validate_image_count, _validate_price, _validate_title


class DummyItem:
    def __init__(self, item_id: str, status: str):
        self.item_id = item_id
        self.status = status
        self.account_id = ""


def test_item_rules():
    assert _parse_image_urls('["/uploads/items/a.jpg","https://x/y.png"]') == ["/uploads/items/a.jpg", "https://x/y.png"]
    assert _normalize_image_urls('["/uploads/items/a.jpg"]') == '["/uploads/items/a.jpg"]'
    assert _validate_title("  abc  ") == "abc"
    try:
        _normalize_image_urls("not-json")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected invalid image json to fail")
    try:
        _normalize_image_urls('["relative.jpg"]')
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected invalid image url to fail")
    try:
        _validate_title("   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected empty title to fail")
    assert _image_count('["a","b","c"]') == 3
    assert _can_delete_item(DummyItem("draft-1", "online")) is True
    assert _can_delete_item(DummyItem("10001", "online")) is False
    assert _can_delete_item(DummyItem("10002", "offline")) is True
    draft_a = _new_draft_item_id("acc1")
    draft_b = _new_draft_item_id("acc1")
    assert draft_a.startswith("draft-acc1-")
    assert draft_b.startswith("draft-acc1-")
    assert draft_a != draft_b
    update_data = ItemUpdateRequest(title="新标题", status="online", publish_status="published")
    assert update_data.model_dump(exclude_none=True) == {"title": "新标题"}
    create_data = ItemCreateRequest(account_id="acc1", item_id="1001", title="新商品", status="online")
    assert "status" not in create_data.model_dump()
    assert _uploaded_image_paths('["/uploads/items/a.jpg","https://x.test/uploads/items/b.png","/tmp/c.jpg"]') == {
        "/uploads/items/a.jpg",
        "/uploads/items/b.png",
    }
    owned_item = DummyItem("1001", "online")
    owned_item.account_id = "acc1"
    assert _is_item_account_conflict(owned_item, "acc1") is False
    assert _is_item_account_conflict(owned_item, "acc2") is True
    assert _is_item_account_conflict(None, "acc1") is False
    _validate_image_count('["1","2","3","4","5","6","7","8"]')
    try:
        _validate_image_count('["1","2","3","4","5","6","7","8","9"]')
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected too many images to fail")
    _validate_price(0)
    _validate_price(9.9)
    try:
        _validate_price(-0.01)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected negative price to fail")
