"""تجميع كل راوترات المستخدم."""
from aiogram import Router

from handlers.user import code_generation, files, misc, pages, project_generator, referral, start, vip, wallet

user_router = Router(name="user")
user_router.include_router(start.router)
user_router.include_router(pages.router)
user_router.include_router(code_generation.router)
user_router.include_router(project_generator.router)
user_router.include_router(vip.router)
user_router.include_router(wallet.router)
user_router.include_router(referral.router)
user_router.include_router(files.router)
user_router.include_router(misc.router)
