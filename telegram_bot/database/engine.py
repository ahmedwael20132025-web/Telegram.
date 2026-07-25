"""
إعداد محرك قاعدة البيانات والجلسات (متوافق مع SQLite و PostgreSQL)
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.database_url, echo=False, future=True)

async_session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """إنشاء جميع الجداول إن لم تكن موجودة."""
    from database import models  # noqa: F401  (لضمان تسجيل كل الجداول)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
