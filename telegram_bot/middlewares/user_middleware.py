"""
Middleware للتحقق من المستخدم: تسجيله تلقائيًا عند أول ظهور، وحظره من المتابعة إن كان محظورًا
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.repository import SettingsRepository, StatisticRepository, UserRepository
from locales import get_text


class UserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data["session"]
        tg_user = event.from_user if isinstance(event, (Message, CallbackQuery)) else None

        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user_repo = UserRepository(session)
        settings_repo = SettingsRepository(session)

        default_credits = await settings_repo.get_int("free_credits_default", 3)
        default_project_credits = await settings_repo.get_int("project_generator_free_default", 1)

        referrer_code = None
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            parts = event.text.split(maxsplit=1)
            if len(parts) > 1:
                referrer_code = parts[1].strip()

        user, created = await user_repo.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            default_free_credits=default_credits,
            referrer_code=referrer_code,
            default_project_free_credits=default_project_credits,
        )

        if created:
            stats_repo = StatisticRepository(session)
            await stats_repo.bump_new_user()

        if user.is_banned:
            lang = user.language
            text = get_text(lang, "banned")
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return None

        data["user"] = user
        return await handler(event, data)
