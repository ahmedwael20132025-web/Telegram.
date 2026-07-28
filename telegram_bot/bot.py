"""
نقطة انطلاق البوت
"""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.engine import init_db
from database.seed import seed_defaults
from handlers.admin import admin_router
from handlers.user import user_router
from middlewares.db_middleware import DatabaseSessionMiddleware
from middlewares.throttling_middleware import ErrorLoggingMiddleware, ThrottlingMiddleware
from middlewares.user_middleware import UserContextMiddleware
from utils.logger import logger
from utils.scheduler import auto_backup_loop, vip_maintenance_loop

bot_instance = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dispatcher = Dispatcher(storage=MemoryStorage())


def register_middlewares() -> None:
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(DatabaseSessionMiddleware())
        observer.outer_middleware(ErrorLoggingMiddleware())
        observer.outer_middleware(ThrottlingMiddleware())
        observer.outer_middleware(UserContextMiddleware())


def register_routers() -> None:
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)


async def on_startup() -> None:
    await init_db()
    await seed_defaults()
    logger.info("تم تشغيل البوت بنجاح.")

    asyncio.create_task(auto_backup_loop())
    asyncio.create_task(vip_maintenance_loop())


async def main() -> None:
    register_middlewares()
    register_routers()
    await on_startup()

    await bot_instance.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot_instance)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت.")
