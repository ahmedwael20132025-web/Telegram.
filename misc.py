"""
ميزات متفرقة: تغيير اللغة، الدعم الفني، قناة البوت (fallback نصي)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database.models import User
from database.repository import SettingsRepository, UserRepository
from keyboards.dynamic import simple_back_keyboard
from locales import SUPPORTED_LANGUAGES, get_text

router = Router(name="misc")

LANGUAGE_LABELS = {"ar": "🇸🇦 العربية", "en": "🇬🇧 English"}


@router.callback_query(F.data == "feat:language")
async def choose_language(callback: CallbackQuery, user: User) -> None:
    rows = [
        [InlineKeyboardButton(text=LANGUAGE_LABELS.get(code, code), callback_data=f"setlang:{code}")]
        for code in SUPPORTED_LANGUAGES
    ]
    rows.append([InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="nav:main")])
    await callback.message.edit_text(
        get_text(user.language, "language_choose"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(callback: CallbackQuery, session, user: User) -> None:
    lang = callback.data.split(":")[1]
    if lang not in SUPPORTED_LANGUAGES:
        return

    user.language = lang
    await session.commit()

    await callback.answer(get_text(lang, "language_changed"))
    await callback.message.edit_text(
        get_text(lang, "language_changed"), reply_markup=simple_back_keyboard(lang)
    )


@router.callback_query(F.data == "feat:support")
async def show_support(callback: CallbackQuery, session, user: User) -> None:
    settings_repo = SettingsRepository(session)
    support_username = await settings_repo.get("support_username", "")
    text = get_text(user.language, "support_text")
    if support_username:
        text += f"\n\n@{support_username}"
    await callback.message.edit_text(text, reply_markup=simple_back_keyboard(user.language))
    await callback.answer()


@router.callback_query(F.data == "feat:bot_channel")
async def show_bot_channel(callback: CallbackQuery, session, user: User) -> None:
    settings_repo = SettingsRepository(session)
    url = await settings_repo.get("bot_channel_url", "")
    name = await settings_repo.get("bot_channel_name", "📢 قناة البوت")

    if not url:
        await callback.answer("⚠️ لم يتم تحديد رابط القناة بعد.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, url=url)],
            [InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="nav:main")],
        ]
    )
    await callback.message.edit_text(get_text(user.language, "bot_channel_text"), reply_markup=keyboard)
    await callback.answer()
