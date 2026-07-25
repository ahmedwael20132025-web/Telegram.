"""
عرض الصفحات الديناميكية التي ينشئها الأدمن (Dynamic Pages & Navigation Builder)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.models import User
from database.repository import PageRepository, SettingsRepository
from keyboards.dynamic import build_menu_keyboard, build_page_navigation_keyboard
from locales import get_text
from services.subscription_service import get_unsubscribed_channels

router = Router(name="pages")


@router.callback_query(F.data.startswith("page:"))
async def open_page_callback(callback: CallbackQuery, session, user: User) -> None:
    code = callback.data.split(":", 1)[1]
    page_repo = PageRepository(session)
    content = await page_repo.get_content(code, user.language)

    if not content:
        await callback.answer("⚠️ هذه الصفحة غير متوفرة حاليًا.", show_alert=True)
        return

    page, translation = content

    if page.access_level == "subscribers_only":
        missing = await get_unsubscribed_channels(callback.bot, session, user.telegram_id)
        if missing:
            await callback.answer(get_text(user.language, "subscribe_required"), show_alert=True)
            return
    elif page.access_level == "admins_only":
        from config import config
        from database.repository import AdminRepository

        is_admin = user.telegram_id in config.super_admins or await AdminRepository(
            session
        ).is_admin(user.telegram_id, config.super_admins)
        if not is_admin:
            await callback.answer(get_text(user.language, "admin_only"), show_alert=True)
            return

    text_parts = []
    if translation.title:
        text_parts.append(f"<b>{translation.title}</b>")
    if translation.description:
        text_parts.append(translation.description)
    if translation.body_text:
        text_parts.append(translation.body_text)
    full_text = "\n\n".join(text_parts) or "—"

    sub_keyboard = await build_menu_keyboard(session, parent_code=page.code)
    keyboard = build_page_navigation_keyboard(sub_keyboard, user.language)

    message = callback.message

    try:
        if translation.image_file_id:
            await message.delete()
            await message.answer_photo(
                translation.image_file_id, caption=full_text, reply_markup=keyboard, parse_mode="HTML"
            )
        elif translation.video_file_id:
            await message.delete()
            await message.answer_video(
                translation.video_file_id, caption=full_text, reply_markup=keyboard, parse_mode="HTML"
            )
        else:
            await message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await message.answer(full_text, reply_markup=keyboard, parse_mode="HTML")

    if translation.document_file_id:
        await callback.bot.send_document(user.telegram_id, translation.document_file_id)

    await callback.answer()


@router.callback_query(F.data.startswith("custom:"))
async def custom_action_callback(callback: CallbackQuery, session, user: User) -> None:
    """إجراء مخصص: يعرض نصًا محفوظًا في الإعدادات باسم custom_action_<target>."""
    target = callback.data.split(":", 1)[1]
    settings_repo = SettingsRepository(session)
    text = await settings_repo.get(f"custom_action_{target}", "")
    if not text:
        await callback.answer("⚠️ لم يتم إعداد هذا الإجراء بعد.", show_alert=True)
        return
    await callback.answer(text, show_alert=True)
