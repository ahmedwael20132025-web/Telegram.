"""
لوحة الأدمن: إدارة المستخدمين
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import WalletOpType
from database.repository import (
    AIRequestRepository,
    PurchaseRepository,
    UserRepository,
)
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard
from states.admin_states import AdminUserStates
from utils.helpers import format_money, is_valid_amount

router = Router(name="admin_users")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:users")
async def ask_user_search(callback: CallbackQuery, state: FSMContext, session) -> None:
    user_repo = UserRepository(session)
    total = await user_repo.count_all()
    await callback.message.edit_text(
        f"👥 إجمالي المستخدمين: {total}\n\nأرسل معرف تيليجرام (ID) للبحث عن مستخدم:",
        reply_markup=admin_back_keyboard(),
    )
    await state.set_state(AdminUserStates.waiting_search_id)
    await callback.answer()


@router.message(AdminUserStates.waiting_search_id)
async def search_user(message: Message, state: FSMContext, session) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ أرسل معرفًا رقميًا صحيحًا.")
        return

    telegram_id = int(message.text.strip())
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        await message.answer("⚠️ لم يتم العثور على هذا المستخدم.")
        return

    purchase_repo = PurchaseRepository(session)
    ai_repo = AIRequestRepository(session)

    purchases = await purchase_repo.list_for_user(user.id)
    referrals_count = await user_repo.count_referrals(user.id)
    ai_count = await ai_repo.count_for_user(user.id)

    text = (
        f"👤 <b>{user.full_name}</b> (@{user.username or '—'})\n"
        f"🆔 {user.telegram_id}\n"
        f"💰 الرصيد: {format_money(user.wallet_balance)}\n"
        f"🎁 عدد الدعوات: {referrals_count}\n"
        f"🧠 عدد طلبات الذكاء الاصطناعي: {ai_count}\n"
        f"🛒 عدد المشتريات: {len(purchases)}\n"
        f"🆓 الأرصدة المجانية المتبقية: {user.free_credits}\n"
        f"🚫 محظور: {'نعم' if user.is_banned else 'لا'}"
    )

    rows = [
        [
            InlineKeyboardButton(
                text="✅ فك الحظر" if user.is_banned else "🚫 حظر",
                callback_data=f"admuser_ban:{telegram_id}",
            ),
            InlineKeyboardButton(text="💰 تعديل الرصيد", callback_data=f"admuser_balance:{telegram_id}"),
        ],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("admuser_ban:"))
async def toggle_ban(callback: CallbackQuery, session) -> None:
    telegram_id = int(callback.data.split(":")[1])
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("⚠️ المستخدم غير موجود.", show_alert=True)
        return

    await user_repo.set_banned(telegram_id, not user.is_banned)
    await callback.answer("✅ تم التحديث")


@router.callback_query(F.data.startswith("admuser_balance:"))
async def ask_balance_amount(callback: CallbackQuery, state: FSMContext) -> None:
    telegram_id = int(callback.data.split(":")[1])
    await state.update_data(target_telegram_id=telegram_id)
    await state.set_state(AdminUserStates.waiting_balance_amount)
    await callback.message.answer(
        "✍️ أرسل المبلغ (استخدم إشارة سالبة للخصم، مثال: -10 أو 10):"
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_balance_amount)
async def apply_balance_change(message: Message, state: FSMContext, session) -> None:
    text = message.text.strip()
    try:
        amount = float(text)
    except ValueError:
        await message.answer("⚠️ قيمة غير صحيحة.")
        return

    data = await state.get_data()
    telegram_id = data.get("target_telegram_id")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        await message.answer("⚠️ المستخدم غير موجود.")
        await state.clear()
        return

    op_type = WalletOpType.admin_gift if amount >= 0 else WalletOpType.admin_deduct
    new_balance = await user_repo.adjust_wallet(user, amount, op_type, note="تعديل يدوي من الأدمن")
    await message.answer(f"✅ تم تحديث الرصيد. الرصيد الجديد: {format_money(new_balance)}")

    try:
        await message.bot.send_message(
            telegram_id, f"💰 تم تعديل رصيدك بواسطة الإدارة. رصيدك الجديد: {format_money(new_balance)}"
        )
    except Exception:
        pass

    await state.clear()


@router.callback_query(F.data == "adm:ban")
async def ban_shortcut(callback: CallbackQuery, state: FSMContext, session) -> None:
    await callback.message.edit_text(
        "🚫 لحظر أو فك حظر مستخدم، ابحث عنه أولًا من قسم 👥 المستخدمون.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()
