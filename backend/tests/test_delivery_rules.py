import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.delivery import _get_owned_item
from app.database import Base
from app.models.account import Account
from app.models.item import Item
from app.models.user import User


async def _run_delivery_rules():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        user_a = User(id=1, username="user-a", hashed_password="x")
        user_b = User(id=2, username="user-b", hashed_password="x")
        account_a = Account(account_id="acc1", owner_id=1, status="active")
        account_b = Account(account_id="acc2", owner_id=2, status="active")
        item_a = Item(item_id="1001", account_id="acc1", title="商品A")
        item_b = Item(item_id="2001", account_id="acc2", title="商品B")
        session.add_all([user_a, user_b, account_a, account_b, item_a, item_b])
        await session.commit()

        assert await _get_owned_item(session, "acc1", "1001", user_a) is not None
        assert await _get_owned_item(session, "acc2", "2001", user_a) is None
        assert await _get_owned_item(session, "acc2", "2001", user_b) is not None

    await engine.dispose()


def test_delivery_rules():
    asyncio.run(_run_delivery_rules())
