from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=20, max_overflow=10)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    from .models.account import Account
    from .models.item import Item
    from .models.keyword_rule import KeywordRule
    from .models.default_reply import DefaultReply
    from .models.confirm_receipt import ConfirmReceiptConfig
    from .models.order import Order
    from .models.statistics import DailyStat
    from .models.delivery_config import DeliveryConfig
    from .models.delivery_log import DeliveryLog
    from .models.publish_log import PublishLog
    from .models.user import User

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from .services.auth import create_default_admin
    async with async_session_maker() as session:
        await create_default_admin(session)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
