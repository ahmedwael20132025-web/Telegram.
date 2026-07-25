"""
ميزة نظام الإحالة (Referral)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.models import User
from database.repository import UserRepository
from keyboards.dynamic import simple_back_keyboard
from locales import get_text

router = Router(name="referral")


@router.callback_query(F.data == "feat:referral")
async def show_referral(callback: CallbackQuery, session, user: User) -> None:
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    user_repo = UserRepository(session)
    count = await user_repo.count_referrals(user.id)

    text = get_text(user.language, "referral_info", link=link, count=count)
    await callback.message.edit_text(text, reply_markup=simple_back_keyboard(user.language))
    await callback.answer()
