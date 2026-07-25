"""
خدمة الإعلان التلقائي في قناة البوت عند نجاح أي عملية (دفع، اشتراك VIP، شراء ملف...)
"""
from __future__ import annotations

from aiogram import Bot

from database.repository import SettingsRepository


async def announce_to_channel(bot: Bot, session, text: str) -> None:
    """يرسل رسالة إلى قناة البوت إذا كان معرّفها مضبوطًا من لوحة الأدمن وكان التبليغ مفعّلاً."""
    settings_repo = SettingsRepository(session)

    if not await settings_repo.get_bool("channel_announcements_enabled", True):
        return

    chat_id = await settings_repo.get("bot_channel_chat_id", "")
    if not chat_id:
        return

    try:
        await bot.send_message(chat_id, text)
    except Exception:
        pass
