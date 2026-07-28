"""
خدمة الإذاعة - إرسال رسالة/صورة/فيديو/ملف لكل المستخدمين مع تقرير النجاح والفشل
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from database.repository import BroadcastLogRepository, UserRepository


@dataclass
class BroadcastResult:
    sent: int
    failed: int


async def broadcast_text(
    bot: Bot,
    session,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> BroadcastResult:
    return await _broadcast(bot, session, "text", text=text, reply_markup=reply_markup)


async def broadcast_photo(
    bot: Bot, session, file_id: str, caption: str = "", reply_markup=None
) -> BroadcastResult:
    return await _broadcast(
        bot, session, "photo", file_id=file_id, caption=caption, reply_markup=reply_markup
    )


async def broadcast_video(
    bot: Bot, session, file_id: str, caption: str = "", reply_markup=None
) -> BroadcastResult:
    return await _broadcast(
        bot, session, "video", file_id=file_id, caption=caption, reply_markup=reply_markup
    )


async def broadcast_document(
    bot: Bot, session, file_id: str, caption: str = "", reply_markup=None
) -> BroadcastResult:
    return await _broadcast(
        bot, session, "document", file_id=file_id, caption=caption, reply_markup=reply_markup
    )


async def _broadcast(bot: Bot, session, kind: str, **kwargs) -> BroadcastResult:
    user_repo = UserRepository(session)
    users = await user_repo.list_all_active()

    sent = 0
    failed = 0
    reply_markup = kwargs.pop("reply_markup", None)

    for user in users:
        try:
            if kind == "text":
                await bot.send_message(user.telegram_id, kwargs["text"], reply_markup=reply_markup)
            elif kind == "photo":
                await bot.send_photo(
                    user.telegram_id, kwargs["file_id"], caption=kwargs.get("caption", ""),
                    reply_markup=reply_markup,
                )
            elif kind == "video":
                await bot.send_video(
                    user.telegram_id, kwargs["file_id"], caption=kwargs.get("caption", ""),
                    reply_markup=reply_markup,
                )
            elif kind == "document":
                await bot.send_document(
                    user.telegram_id, kwargs["file_id"], caption=kwargs.get("caption", ""),
                    reply_markup=reply_markup,
                )
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            failed += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    log_repo = BroadcastLogRepository(session)
    await log_repo.create(sent, failed)

    return BroadcastResult(sent=sent, failed=failed)
