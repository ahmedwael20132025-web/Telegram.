"""
لوحة الأدمن: طلبات السحب والنسخ الاحتياطي
"""
from __future__ import annotations

from aiogram.types import FSInputFile
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database.models import PaymentStatus, WalletOpType
from database.repository import UserRepository, WithdrawRepository
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard
from services.backup_service import create_backup, list_backups, restore_backup
from utils.helpers import format_money

router = Router(name="admin_finance_ops")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:withdrawals")
async def list_withdrawals(callback: CallbackQuery, session) -> None:
    repo = WithdrawRepository(session)
    pending = await repo.list_pending()

    if not pending:
        await callback.message.edit_text("💸 لا توجد طلبات سحب معلّقة.", reply_markup=admin_back_keyboard())
        await callback.answer()
        return

    request = pending[0]
    from sqlalchemy import select
    from database.models import User

    result = await session.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    text = (
        f"💸 طلب سحب #{request.id}\nالمستخدم: {user.telegram_id if user else '—'}\n"
        f"المبلغ: {format_money(request.amount)}\nالبيانات: {request.details}"
    )
    rows = [
        [InlineKeyboardButton(text="✅ موافقة", callback_data=f"wd_approve:{request.id}"),
         InlineKeyboardButton(text="❌ رفض", callback_data=f"wd_reject:{request.id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("wd_approve:"))
async def approve_withdraw(callback: CallbackQuery, session) -> None:
    request_id = int(callback.data.split(":")[1])
    repo = WithdrawRepository(session)
    request = await repo.set_status(request_id, PaymentStatus.approved)
    if request:
        from sqlalchemy import select
        from database.models import User

        result = await session.execute(select(User).where(User.id == request.user_id))
        user = result.scalar_one_or_none()
        if user:
            try:
                await callback.bot.send_message(user.telegram_id, "✅ تم تنفيذ طلب السحب الخاص بك.")
            except Exception:
                pass
    await callback.answer("✅ تم القبول")
    await list_withdrawals(callback, session)


@router.callback_query(F.data.startswith("wd_reject:"))
async def reject_withdraw(callback: CallbackQuery, session) -> None:
    request_id = int(callback.data.split(":")[1])
    repo = WithdrawRepository(session)
    request = await repo.get(request_id)

    if request:
        await repo.set_status(request_id, PaymentStatus.rejected)
        user_repo = UserRepository(session)
        from sqlalchemy import select
        from database.models import User

        result = await session.execute(select(User).where(User.id == request.user_id))
        user = result.scalar_one_or_none()
        if user:
            await user_repo.adjust_wallet(user, request.amount, WalletOpType.refund, note="رفض طلب سحب")
            try:
                await callback.bot.send_message(
                    user.telegram_id, "❌ تم رفض طلب السحب وتمت إعادة المبلغ لمحفظتك."
                )
            except Exception:
                pass

    await callback.answer("✅ تم الرفض")
    await list_withdrawals(callback, session)


@router.callback_query(F.data == "adm:backup")
async def backup_menu(callback: CallbackQuery) -> None:
    backups = list_backups()
    rows = [
        [InlineKeyboardButton(text="💾 إنشاء نسخة احتياطية الآن", callback_data="backup_now")],
    ]
    for backup in backups[:5]:
        rows.append([InlineKeyboardButton(text=f"⏮️ استعادة {backup.name}", callback_data=f"backup_restore:{backup.name}")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])

    await callback.message.edit_text(
        f"💾 النسخ الاحتياطي\nعدد النسخ المتاحة: {len(backups)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data == "backup_now")
async def backup_now(callback: CallbackQuery) -> None:
    path = create_backup()
    if not path:
        await callback.answer("⚠️ فشل إنشاء النسخة الاحتياطية.", show_alert=True)
        return
    await callback.message.answer_document(FSInputFile(path), caption="💾 نسخة احتياطية جديدة")
    await callback.answer("✅ تم")


@router.callback_query(F.data.startswith("backup_restore:"))
async def backup_restore(callback: CallbackQuery) -> None:
    filename = callback.data.split(":", 1)[1]
    from config import config

    backup_path = config.backups_dir / filename
    success = restore_backup(backup_path)
    if success:
        await callback.answer("✅ تم استعادة النسخة. يُنصح بإعادة تشغيل البوت.", show_alert=True)
    else:
        await callback.answer("⚠️ فشلت عملية الاستعادة.", show_alert=True)
