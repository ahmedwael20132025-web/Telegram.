"""
Middleware للحماية من السبام (Rate Limiting) باستخدام نافذة زمنية بسيطة في الذاكرة
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.repository import LogRepository


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit_seconds: float = 0.7):
        self.rate_limit_seconds = rate_limit_seconds
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = event.from_user if isinstance(event, (Message, CallbackQuery)) else None
        if tg_user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last_seen.get(tg_user.id, 0.0)

        if now - last < self.rate_limit_seconds:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ برجاء الانتظار قليلاً...", show_alert=False)
            return None

        self._last_seen[tg_user.id] = now
        return await handler(event, data)


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:  # noqa: BLE001
            session = data.get("session")
            if session is not None:
                try:
                    await LogRepository(session).add(
                        message=str(exc), level="error", source="handler"
                    )
                except Exception:  # noqa: BLE001
                    pass
            raise
