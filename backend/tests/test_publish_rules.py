from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.publisher import MAX_PUBLISH_IMAGES, _copy_item_for_republish, _extract_item_id_from_url, _image_count, _merge_item_for_publish, _normalize_publish_result, _parse_image_urls, _summarize_publish_page_text


class DummyItem:
    def __init__(self, item_id="", account_id="", title="", description="", image_urls="[]", price=0, status="draft", publish_status="draft", publish_error="err", url=""):
        self.item_id = item_id
        self.account_id = account_id
        self.title = title
        self.description = description
        self.image_urls = image_urls
        self.price = price
        self.status = status
        self.publish_status = publish_status
        self.publish_error = publish_error
        self.url = url


def test_publish_rules():
    assert MAX_PUBLISH_IMAGES == 8
    assert _parse_image_urls('["a","b"]') == ["a", "b"]
    assert _image_count('["a","b"]') == 2

    target = DummyItem(title="", description="", image_urls='["a"]', price=0, url="", publish_status="draft", publish_error="x")
    source = DummyItem(title="标题", description="描述", image_urls='["a","b"]', price=12.5, url="http://x")
    _merge_item_for_publish(target, source)
    assert target.title == "标题"
    assert target.description == "描述"
    assert target.image_urls == '["a","b"]'
    assert target.price == 12.5
    assert target.url == "http://x"
    assert target.publish_status == "published"
    assert target.publish_error is None

    republish_target = DummyItem()
    republish_source = DummyItem(account_id="acc1", title="标题2", description="描述2", image_urls='["c"]', price=8.8)
    _copy_item_for_republish(republish_target, republish_source, "1001", None)
    assert republish_target.item_id == "1001"
    assert republish_target.account_id == "acc1"
    assert republish_target.title == "标题2"
    assert republish_target.image_urls == '["c"]'
    assert republish_target.status == "online"
    assert republish_target.publish_status == "published"
    assert republish_target.publish_error is None
    assert republish_target.url == "https://www.goofish.com/item/1001"

    draft_result = _normalize_publish_result("draft-acc1-1", {"success": True, "message": "", "item_id": None})
    assert draft_result["success"] is False
    assert "商品ID" in draft_result["message"]

    online_result = _normalize_publish_result("1001", {"success": True, "message": "", "item_id": None})
    assert online_result["success"] is False
    assert online_result["message"]

    failed_result = _normalize_publish_result("draft-acc1-1", {"success": False, "message": ""})
    assert failed_result["success"] is False
    assert failed_result["message"]
    assert _summarize_publish_page_text("标题不能为空\n请选择图片\n普通说明") == "标题不能为空；请选择图片"

    assert _extract_item_id_from_url("https://www.goofish.com/item/123456") == "123456"
    assert _extract_item_id_from_url("https://www.goofish.com/item?id=2233") == "2233"
    assert _extract_item_id_from_url("https://www.goofish.com/publish?item_id=9988") == "9988"

    parsed_result = _normalize_publish_result(
        "draft-acc1-1",
        {"success": True, "message": "", "item_id": None, "item_url": "https://www.goofish.com/item/123456"},
    )
    assert parsed_result["success"] is True
    assert parsed_result["item_id"] == "123456"

    import asyncio
    asyncio.run(_run_publish_precheck_rules())
    asyncio.run(_run_offline_fallback_rule())


async def _run_publish_precheck_rules():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database import Base
    from app.models.account import Account
    from app.models.item import Item
    from app.services.publisher import publish_item

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        account = Account(account_id="acc-empty-cookie", owner_id=1, cookie="")
        item = Item(item_id="draft-empty-cookie", account_id="acc-empty-cookie", title="draft", publish_status="publishing")
        session.add_all([account, item])
        await session.commit()

        result = await publish_item(session, "draft-empty-cookie", 1)
        assert result["success"] is False
        refreshed = (await session.execute(select(Item).where(Item.item_id == "draft-empty-cookie"))).scalar_one()
        assert refreshed.publish_status == "failed"
        assert refreshed.publish_error == "Account cookie is empty, please login again"

    await engine.dispose()


async def _run_offline_fallback_rule():
    import app.services.publisher as publisher

    calls = []

    async def fake_detail_page(cookies_str: str, item_id: str, item_url: str = "") -> bool:
        calls.append((cookies_str, item_id, item_url))
        return True

    class FakeResponse:
        headers = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self, content_type=None):
            return {"ret": ["FAIL_BIZ_IDLE_USER_UNAUTHORIZED::无权限访问"], "data": {}}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    original_session = publisher.aiohttp.ClientSession
    original_detail = publisher._offline_item_via_detail_page
    publisher.aiohttp.ClientSession = FakeSession
    publisher._offline_item_via_detail_page = fake_detail_page
    try:
        result = await publisher._offline_item("acc1", "foo=bar", "1001", "https://www.goofish.com/item?id=1001")
        assert result is True
        assert calls == [("foo=bar", "1001", "https://www.goofish.com/item?id=1001")]
    finally:
        publisher.aiohttp.ClientSession = original_session
        publisher._offline_item_via_detail_page = original_detail
