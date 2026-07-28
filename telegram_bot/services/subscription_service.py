"""
خدمة التحقق من الاشتراك الإجباري في القنوات
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from database.models import Channel
from database.repository import ChannelRepository, SettingsRepository


async def get_unsubscribed_channels(
    bot: Bot, session, telegram_id: int, user_id: int | None = None
) -> list[Channel]:
    settings_repo = SettingsRepository(session)
    if not await settings_repo.get_bool("forced_subscription_enabled", False):
        return []

    if user_id is not None:
        from services.vip_service import get_vip_status

        is_vip, _ = await get_vip_status(session, user_id)
        if is_vip:
            return []

    channel_repo = ChannelRepository(session)
    channels = await channel_repo.list_active()
    missing: list[Channel] = []

    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.chat_id, telegram_id)
            if member.status in ("left", "kicked"):
                missing.append(channel)
        except TelegramBadRequest:
            missing.append(channel)

    return missing
