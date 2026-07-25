"""
لوحة الأدمن: الإذاعة (نص، صورة، فيديو، ملف)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard
from services.broadcast_service import (
    broadcast_document,
    broadcast_photo,
    broadcast_text,
    broadcast_video,
)
from states.admin_states import AdminBroadcastStates

router = Router(name="admin_broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:broadcast")
async def ask_broadcast_content(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "📣 أرسل الآن محتوى الإذاعة: نص، صورة، فيديو أو ملف (مع كابشن اختياري).",
        reply_markup=admin_back_keyboard(),
    )
    await state.set_state(AdminBroadcastStates.waiting_content)
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_content)
async def send_broadcast(message: Message, state: FSMContext, session) -> None:
    status = await message.answer("⏳ جاري الإرسال...")

    if message.photo:
        result = await broadcast_photo(message.bot, session, message.photo[-1].file_id, message.caption or "")
    elif message.video:
        result = await broadcast_video(message.bot, session, message.video.file_id, message.caption or "")
    elif message.document:
        result = await broadcast_document(message.bot, session, message.document.file_id, message.caption or "")
    elif message.text:
        result = await broadcast_text(message.bot, session, message.text)
    else:
        await status.edit_text("⚠️ نوع المحتوى غير مدعوم.")
        await state.clear()
        return

    await status.edit_text(
        f"✅ تم إرسال الإذاعة.\nنجح: {result.sent}\nفشل: {result.failed}"
    )
    await state.clear()
