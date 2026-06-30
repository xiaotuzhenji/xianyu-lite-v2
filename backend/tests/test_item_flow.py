import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.items import (
    ItemCreateRequest,
    _can_delete_item,
    _cleanup_uploaded_images,
    _delete_delivery_config,
    _get_owned_item,
    _move_delivery_config,
    create_item,
)
from app.database import Base
from app.models.account import Account
from app.models.delivery_config import DeliveryConfig
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
        try:
            await create_item(ItemCreateRequest(account_id="acc1", item_id="1003", title="manual id"), session, user_a)
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("expected create item with manual item_id to fail")
        _cleanup_uploaded_images('["/uploads/items/a.jpg","/tmp/b.jpg"]')
        config = DeliveryConfig(account_id="acc1", item_id="draft-acc1-1", delivery_content="delivery content")
        session.add(config)
        await session.commit()
        await _move_delivery_config(session, "acc1", "draft-acc1-1", "1003")
        await session.commit()
        moved_config = (
            await session.execute(
                select(DeliveryConfig).where(
                    DeliveryConfig.account_id == "acc1",
                    DeliveryConfig.item_id == "1003",
                )
            )
        ).scalar_one_or_none()
        assert moved_config is not None
        assert moved_config.delivery_content == "delivery content"
        await _delete_delivery_config(session, "acc1", "1003")
        await session.commit()
        removed_config = (
            await session.execute(
                select(DeliveryConfig).where(
                    DeliveryConfig.account_id == "acc1",
                    DeliveryConfig.item_id == "1003",
                )
            )
        ).scalar_one_or_none()
        assert removed_config is None

    await engine.dispose()


def test_item_flow():
    asyncio.run(_run_item_flow())
