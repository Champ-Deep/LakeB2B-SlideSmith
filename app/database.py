"""
Async SQLAlchemy engine, session factory, and table-creation helper.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Engine + session factory (created lazily at startup)
engine = None
async_session: async_sessionmaker[AsyncSession] | None = None


async def init_db():
    """Create engine, session factory, and all tables."""
    global engine, async_session

    if not settings.database_url:
        return  # No DB configured; skip gracefully

    # Import models so Base.metadata knows about all tables
    import app.db_models  # noqa: F401

    engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
