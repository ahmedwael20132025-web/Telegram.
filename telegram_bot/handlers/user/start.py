"""
معالج أمر البدء /start، وعرض القائمة الرئيسية، والتحقق من الاشتراك الإجباري
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from database.models import User
from database.repository import SettingsRepository
from keyboards.dynamic import build_menu_keyboard, simple_back_keyboard
from locales import get_text
from services.subscription_service import get_unsubscribed_channels

router = Router(name="start")


async def _render_subscription_prompt(session, user: User) -> tuple[str, "InlineKeyboardMarkup"]:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from database.repository import ChannelRepository

    channels = await ChannelRepository(session).list_active()
    rows = [
        [InlineKeyboardButton(text=f"📢 {c.title}", url=c.invite_link)] for c in channels
    ]
    rows.append(
        [InlineKeyboardButton(
            text=get_text(user.language, "subscribe_check_button"), callback_data="nav:check_sub"
        )]
    )
    text = get_text(user.language, "subscribe_required")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def show_main_menu(bot_message_target, session, user: User, edit: bool = False) -> None:
    settings_repo = SettingsRepository(session)
    bot_name = await settings_repo.get("bot_name", "البوت")

    text = get_text(
        user.language, "welcome", name=user.full_name or "صديقي", bot_name=bot_name
    )
    keyboard = await build_menu_keyboard(session, menu="main")

    from config import config
    from database.repository import AdminRepository

    is_admin = user.telegram_id in config.super_admins or await AdminRepository(session).is_admin(
        user.telegram_id, config.super_admins
    )
    if is_admin:
        from aiogram.types import InlineKeyboardButton

        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="🛠️ لوحة الأدمن", callback_data="adm:main")]
        )

    if edit:
        await bot_message_target.edit_text(text, reply_markup=keyboard)
    else:
        await bot_message_target.answer(text, reply_markup=keyboard)


@router.message(CommandStart())
async def start_handler(message: Message, session, user: User) -> None:
    unsubscribed = await get_unsubscribed_channels(message.bot, session, user.telegram_id, user_id=user.id)
    if unsubscribed:
        text, keyboard = await _render_subscription_prompt(session, user)
        await message.answer(text, reply_markup=keyboard)
        return

    await show_main_menu(message, session, user, edit=False)


@router.callback_query(F.data == "nav:check_sub")
async def check_subscription_callback(callback: CallbackQuery, session, user: User) -> None:
    unsubscribed = await get_unsubscribed_channels(callback.bot, session, user.telegram_id, user_id=user.id)
    if unsubscribed:
        await callback.answer(get_text(user.language, "subscribe_still_missing"), show_alert=True)
        return

    await show_main_menu(callback.message, session, user, edit=True)
    await callback.answer()


@router.callback_query(F.data == "nav:main")
async def back_to_main_callback(callback: CallbackQuery, session, user: User) -> None:
    await show_main_menu(callback.message, session, user, edit=True)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
