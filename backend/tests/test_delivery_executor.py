import asyncio
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.internal import OrderEventRequest, upsert_order_event
from app.database import Base
from app.models.delivery_config import DeliveryConfig
from app.models.delivery_log import DeliveryLog
from app.models.order import Order
from app.services.delivery import DeliveryExecutor


async def _with_db(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with session_maker() as session:
            await fn(session)
    finally:
        await engine.dispose()


async def _test_internal_event_delivers_configured_item(session):
    sent = []
    original_send = DeliveryExecutor._send_text

    async def fake_send(self, account_id: str, buyer_id: str, content: str, item_id: str = ""):
        sent.append((account_id, buyer_id, content, item_id))
        return True, ""

    DeliveryExecutor._send_text = fake_send
    try:
        session.add(DeliveryConfig(account_id="acc1", item_id="item1", delivery_content="发货内容"))
        await session.commit()

        result = await upsert_order_event(
            OrderEventRequest(account_id="acc1", order_id="order-1", item_id="item1", buyer_id="buyer1"),
            session,
        )

        order = (await session.execute(select(Order).where(Order.order_id == "order-1"))).scalar_one()
        log = (await session.execute(select(DeliveryLog).where(DeliveryLog.order_id == "order-1"))).scalar_one()

        assert result["delivered"] is True
        assert order.status == "shipped"
        assert log.status == "success"
        assert sent == [("acc1", "buyer1", "发货内容", "item1")]
    finally:
        DeliveryExecutor._send_text = original_send


async def _test_fallback_duplicate_is_not_sent_twice(session):
    sent = []

    async def fake_send(account_id: str, buyer_id: str, content: str, item_id: str = ""):
        sent.append((account_id, buyer_id, content, item_id))
        return True, ""

    session.add_all([
        DeliveryConfig(account_id="acc1", item_id="item1", delivery_content="发货内容"),
        Order(order_id="ws-old", account_id="acc1", item_id="item1", buyer_id="buyer1", status="shipped"),
        DeliveryLog(
            order_id="ws-old",
            account_id="acc1",
            item_id="item1",
            buyer_id="buyer1",
            status="success",
            content="发货内容",
            sent_at=datetime.utcnow(),
        ),
        Order(order_id="ws-new", account_id="acc1", item_id="item1", buyer_id="buyer1", status="paid"),
    ])
    await session.commit()

    order = (await session.execute(select(Order).where(Order.order_id == "ws-new"))).scalar_one()
    executor = DeliveryExecutor(session)
    executor._send_text = fake_send
    log = await executor.deliver_order(order)

    logs = (await session.execute(select(DeliveryLog).order_by(DeliveryLog.order_id))).scalars().all()
    assert log.order_id == "ws-new"
    assert log.status == "success"
    assert order.status == "shipped"
    assert sent == []
    assert [row.order_id for row in logs] == ["ws-new", "ws-old"]


async def _test_missing_item_or_buyer_records_failure(session):
    session.add_all([
        Order(order_id="missing-item", account_id="acc1", item_id="", buyer_id="buyer1", status="paid"),
        Order(order_id="missing-buyer", account_id="acc1", item_id="item1", buyer_id="", status="paid"),
    ])
    await session.commit()

    executor = DeliveryExecutor(session)
    item_order = (await session.execute(select(Order).where(Order.order_id == "missing-item"))).scalar_one()
    buyer_order = (await session.execute(select(Order).where(Order.order_id == "missing-buyer"))).scalar_one()

    item_log = await executor.deliver_order(item_order)
    buyer_log = await executor.deliver_order(buyer_order)

    assert item_log.status == "failed"
    assert "item_id" in item_log.error
    assert buyer_log.status == "failed"
    assert "buyer_id" in buyer_log.error


def test_internal_event_delivers_configured_item():
    asyncio.run(_with_db(_test_internal_event_delivers_configured_item))


def test_fallback_duplicate_is_not_sent_twice():
    asyncio.run(_with_db(_test_fallback_duplicate_is_not_sent_twice))


def test_missing_item_or_buyer_records_failure():
    asyncio.run(_with_db(_test_missing_item_or_buyer_records_failure))


if __name__ == "__main__":
    test_internal_event_delivers_configured_item()
    test_fallback_duplicate_is_not_sent_twice()
    test_missing_item_or_buyer_records_failure()
