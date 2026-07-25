"""
فلتر التحقق من صلاحية الأدمن
"""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import config
from database.repository import AdminRepository


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, session) -> bool:
        user_id = event.from_user.id
        if user_id in config.super_admins:
            return True
        repo = AdminRepository(session)
        return await repo.is_admin(user_id, config.super_admins)


class IsSuperAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id in config.super_admins
