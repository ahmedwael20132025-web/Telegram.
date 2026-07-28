"""
ميزة نظام الإحالة (Referral)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.models import User
from database.repository import SettingsRepository, UserRepository
from keyboards.dynamic import simple_back_keyboard
from locales import get_text
from utils.helpers import format_money

router = Router(name="referral")


@router.callback_query(F.data == "feat:referral")
async def show_referral(callback: CallbackQuery, session, user: User) -> None:
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    user_repo = UserRepository(session)
    count = await user_repo.count_referrals(user.id)

    settings_repo = SettingsRepository(session)
    reward_type = await settings_repo.get("referral_reward_type", "wallet")
    reward_value = await settings_repo.get_float("referral_reward_value", 5)
    min_invites = await settings_repo.get_int("referral_min_invites", 1)

    if reward_type == "free_credit":
        reward_line = f"{int(reward_value)} كود إنشاء مجاني"
    else:
        reward_line = format_money(reward_value)

    text = get_text(user.language, "referral_info", link=link, count=count)
    text += f"\n\n🎯 مكافأتك عند كل دعوة مؤهلة: {reward_line}"
    if min_invites > 1:
        text += f"\n📌 يلزم دعوة {min_invites} أشخاص على الأقل لصرف المكافأة."

    await callback.message.edit_text(text, reply_markup=simple_back_keyboard(user.language))
    await callback.answer()
