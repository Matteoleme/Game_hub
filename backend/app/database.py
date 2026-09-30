from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


settings = get_settings()
database_url = make_url(settings.database_url)
if database_url.drivername.startswith("sqlite") and database_url.database:
    from pathlib import Path

    Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)

engine: AsyncEngine = create_async_engine(settings.database_url, future=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def initialize_database() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("PRAGMA journal_mode=WAL"))
        from app.auth.models import AuthSession, User  # noqa: F401
        from app.rooms.persistence_models import GameRecord, RoomRecord  # noqa: F401

        await connection.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
