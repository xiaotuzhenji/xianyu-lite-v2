import asyncio
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.accounts import AccountResponse, _get_owned_account
from app.database import Base
from app.models.account import Account
from app.models.user import User


async def _run_account_rules():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        user_a = User(id=1, username="user-a", hashed_password="x")
        user_b = User(id=2, username="user-b", hashed_password="x")
        account_a = Account(account_id="acc1", owner_id=1, status="active")
        account_b = Account(account_id="acc2", owner_id=2, status="active")
        session.add_all([user_a, user_b, account_a, account_b])
        await session.commit()

        assert await _get_owned_account(session, "acc1", user_a) is not None
        assert await _get_owned_account(session, "acc2", user_a) is None
        assert await _get_owned_account(session, "acc2", user_b) is not None

    await engine.dispose()


def test_account_rules():
    asyncio.run(_run_account_rules())


def test_account_response_accepts_datetime():
    account = Account(
        id=1,
        account_id="acc1",
        owner_id=1,
        status="active",
        last_active_at=datetime(2026, 6, 30, 12, 0, 0),
    )
    data = AccountResponse.model_validate(account)
    assert data.last_active_at is not None
