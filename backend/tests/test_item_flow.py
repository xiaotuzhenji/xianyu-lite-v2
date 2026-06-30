import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.items import _can_delete_item, _cleanup_uploaded_images, _get_owned_item
from app.database import Base
from app.models.account import Account
from app.models.item import Item
from app.models.user import User


async def _run_item_flow():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        user_a = User(id=1, username="user-a", hashed_password="x")
        user_b = User(id=2, username="user-b", hashed_password="x")
        account_a = Account(account_id="acc1", owner_id=1, status="active")
        account_b = Account(account_id="acc2", owner_id=2, status="active")
        draft = Item(item_id="draft-acc1-1", account_id="acc1", title="草稿", status="draft", publish_status="draft")
        online = Item(item_id="1001", account_id="acc1", title="在售", status="online", publish_status="published")
        offline = Item(item_id="1002", account_id="acc1", title="下架", status="offline", publish_status="draft")
        other_item = Item(item_id="2001", account_id="acc2", title="其他用户商品", status="online", publish_status="published")
        session.add_all([user_a, user_b, account_a, account_b, draft, online, offline, other_item])
        await session.commit()

        assert _can_delete_item(draft) is True
        assert _can_delete_item(online) is False
        assert _can_delete_item(offline) is True
        assert await _get_owned_item(session, "1001", user_a) is not None
        assert await _get_owned_item(session, "2001", user_a) is None
        assert await _get_owned_item(session, "2001", user_b) is not None
        _cleanup_uploaded_images('["/uploads/items/a.jpg","/tmp/b.jpg"]')

    await engine.dispose()


def test_item_flow():
    asyncio.run(_run_item_flow())
