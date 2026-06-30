import asyncio
import os
from pathlib import Path
import sys

os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DATABASE", "xianyu_lite_test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("SECRET_KEY", "test-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.models.user import User
from app.models.item import Item
from app.services.auth import hash_password, create_access_token, decode_access_token, authenticate_user
from app.api.items import _can_delete_item


async def _run_api_smoke():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        user = User(username="admin", hashed_password=hash_password("123456"), is_admin=True)
        item = Item(item_id="1001", account_id="acc1", status="online", publish_status="published")
        draft_item = Item(item_id="draft-acc1-1", account_id="acc1", status="online", publish_status="draft")
        session.add_all([user, item, draft_item])
        await session.commit()

        authed = await authenticate_user(session, "admin", "123456")
        assert authed is not None and authed.username == "admin"
        token = create_access_token({"sub": str(authed.id), "username": authed.username})
        assert decode_access_token(token)["username"] == "admin"
        assert _can_delete_item(draft_item) is True
        assert _can_delete_item(item) is False
        rows = (await session.execute(select(User))).scalars().all()
        assert len(rows) == 1
    await engine.dispose()


def test_api_smoke():
    asyncio.run(_run_api_smoke())
