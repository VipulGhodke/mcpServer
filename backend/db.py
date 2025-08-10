from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.engine import Connection

from .core.config import settings
from .models import Base


engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    """FastAPI dependency that yields an AsyncSession."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        # First ensure tables exist based on current models
        await conn.run_sync(Base.metadata.create_all)
        # Then apply minimal pragmatic migrations for legacy DBs
        if conn.engine.dialect.name == "sqlite":
            await _migrate_sqlite(conn)


async def _migrate_sqlite(conn: Connection) -> None:  # type: ignore[type-arg]
    # Helper: check table exists (async)
    async def _table_exists(name: str) -> bool:
        res = await conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        )
        row = res.fetchone()
        return bool(row and row[0] == name)

    # Add missing columns to profiles (learning_language, native_language) if table exists
    if await _table_exists("profiles"):
        rows = (await conn.exec_driver_sql("PRAGMA table_info('profiles')")).all()
        existing_cols = {r[1] for r in rows}
        if "learning_language" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN learning_language VARCHAR(8)")
        if "native_language" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN native_language VARCHAR(8)")
        if "current_difficulty" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN current_difficulty INTEGER DEFAULT 1 NOT NULL")
        if "correct_streak" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN correct_streak INTEGER DEFAULT 0 NOT NULL")
        if "hearts_last_refill_at" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN hearts_last_refill_at TIMESTAMP WITH TIME ZONE")

    # Lessons table migrations if exists
    if await _table_exists("lessons"):
        rows = (await conn.exec_driver_sql("PRAGMA table_info('lessons')")).all()
        existing_cols = {r[1] for r in rows}
        if "meta" not in existing_cols and "metadata" in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE lessons RENAME COLUMN metadata TO meta")
        if "lang" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE lessons ADD COLUMN lang VARCHAR(8)")

    # Media events table
    if not await _table_exists("media_events"):
        # Ensure new table exists if created via models; create_all handles this, so this is just a guard
        await conn.run_sync(Base.metadata.create_all)

    # Attempts table migrations if exists
    if await _table_exists("attempts"):
        rows = (await conn.exec_driver_sql("PRAGMA table_info('attempts')")).all()
        existing_cols = {r[1] for r in rows}
        if "level" not in existing_cols:
            await conn.exec_driver_sql("ALTER TABLE attempts ADD COLUMN level INTEGER")


