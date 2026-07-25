"""
لوحة الأدمن: طرق الدفع، والموافقة/الرفض على المدفوعات اليدوية
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import PaymentStatus, WalletOpType
from database.repository import (
    CodeFileRepository,
    PaymentMethodRepository,
    PaymentRepository,
    PurchaseRepository,
    StatisticRepository,
    UserRepository,
    VipPlanRepository,
)
from filters.admin_filter import IsAdmin
from services.referral_service import process_referral_reward
from services.vip_service import activate_subscription
from states.admin_states import AdminPaymentMethodStates
from utils.helpers import is_valid_amount

router = Router(name="admin_payments")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:payments")
async def list_payment_methods(callback: CallbackQuery, session) -> None:
    repo = PaymentMethodRepository(session)
    methods = await repo.list_all()
    payment_repo = PaymentRepository(session)
    pending = await payment_repo.list_pending()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if m.is_active else '🚫'} {m.name}", callback_data=f"pm_adm:{m.id}"
        )]
        for m in methods
    ]
    rows.append([InlineKeyboardButton(text="➕ إضافة طريقة دفع", callback_data="pm_new")])
    rows.append([InlineKeyboardButton(text=f"⏳ مدفوعات قيد المراجعة ({len(pending)})", callback_data="pm_pending")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])

    await callback.message.edit_text("💳 طرق الدفع", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "pm_new")
async def create_method_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل اسم طريقة الدفع (مثال: 📱 فودافون كاش):")
    await state.set_state(AdminPaymentMethodStates.waiting_name)
    await callback.answer()


@router.message(AdminPaymentMethodStates.waiting_name)
async def method_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await message.answer("💰 أرسل السعر الافتراضي:")
    await state.set_state(AdminPaymentMethodStates.waiting_price)


@router.message(AdminPaymentMethodStates.waiting_price)
async def method_price(message: Message, state: FSMContext) -> None:
    if not is_valid_amount(message.text):
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return
    await state.update_data(price=float(message.text.strip()))
    await message.answer("📝 أرسل تعليمات الدفع التي ستظهر للمستخدم:")
    await state.set_state(AdminPaymentMethodStates.waiting_instructions)


@router.message(AdminPaymentMethodStates.waiting_instructions)
async def method_instructions(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    repo = PaymentMethodRepository(session)
    code = data["name"].lower().replace(" ", "_")[:32]
    method = await repo.create(
        code=code, name=data["name"], price=data["price"], currency="EGP",
        instructions=message.text.strip(),
    )
    await message.answer(f"✅ تم إضافة طريقة الدفع {method.name}.")
    await state.clear()


@router.callback_query(F.data.startswith("pm_adm:"))
async def manage_method(callback: CallbackQuery, session) -> None:
    method_id = int(callback.data.split(":")[1])
    repo = PaymentMethodRepository(session)
    method = await repo.get(method_id)
    if not method:
        await callback.answer("⚠️ غير موجود.", show_alert=True)
        return

    text = f"💳 <b>{method.name}</b>\nالسعر: {method.price} {method.currency}\n{method.instructions}"
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"pm_toggle:{method_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:payments")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("pm_toggle:"))
async def toggle_method(callback: CallbackQuery, session) -> None:
    method_id = int(callback.data.split(":")[1])
    repo = PaymentMethodRepository(session)
    await repo.toggle(method_id)
    await callback.answer("✅ تم التحديث")
    await manage_method(callback, session)


@router.callback_query(F.data == "pm_pending")
async def list_pending_payments(callback: CallbackQuery, session) -> None:
    repo = PaymentRepository(session)
    pending = await repo.list_pending()

    if not pending:
        await callback.answer("✅ لا توجد مدفوعات قيد المراجعة.", show_alert=True)
        return

    payment = pending[0]
    user_repo = UserRepository(session)
    from sqlalchemy import select
    from database.models import User

    result = await session.execute(select(User).where(User.id == payment.user_id))
    user = result.scalar_one_or_none()

    text = (
        f"💳 طلب #{payment.id}\nالمستخدم: {user.telegram_id if user else '—'}\n"
        f"الغرض: {payment.purpose}\nالمبلغ: {payment.amount}\nالمرجع: {payment.reference or '—'}"
    )
    rows = [
        [InlineKeyboardButton(text="✅ قبول", callback_data=f"pay_approve:{payment.id}"),
         InlineKeyboardButton(text="❌ رفض", callback_data=f"pay_reject:{payment.id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:payments")],
    ]

    if payment.proof_file_id:
        await callback.message.answer_photo(payment.proof_file_id, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    else:
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("pay_approve:"))
async def approve_payment(callback: CallbackQuery, session) -> None:
    payment_id = int(callback.data.split(":")[1])
    await _decide_payment(callback, session, payment_id, PaymentStatus.approved)


@router.callback_query(F.data.startswith("pay_reject:"))
async def reject_payment(callback: CallbackQuery, session) -> None:
    payment_id = int(callback.data.split(":")[1])
    await _decide_payment(callback, session, payment_id, PaymentStatus.rejected)


async def _decide_payment(callback: CallbackQuery, session, payment_id: int, status: str) -> None:
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.set_status(payment_id, status, callback.from_user.id)
    if not payment:
        await callback.answer("⚠️ الطلب غير موجود.", show_alert=True)
        return

    from sqlalchemy import select
    from database.models import User

    result = await session.execute(select(User).where(User.id == payment.user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer()
        return

    if status == PaymentStatus.approved:
        await _fulfill_payment(session, user, payment, bot=callback.bot)
        try:
            await callback.bot.send_message(user.telegram_id, "✅ تم تأكيد دفعتك بنجاح!")
        except Exception:
            pass
    else:
        try:
            await callback.bot.send_message(user.telegram_id, "❌ تم رفض عملية الدفع الخاصة بك.")
        except Exception:
            pass

    await callback.message.edit_text(f"تم {'قبول' if status == PaymentStatus.approved else 'رفض'} الطلب #{payment_id}.")
    await callback.answer()


async def _fulfill_payment(session, user, payment, bot=None) -> None:
    purpose = payment.purpose
    stats_repo = StatisticRepository(session)
    from services.announcer import announce_to_channel

    if purpose == "code_generation":
        await stats_repo.add_revenue(payment.amount)
        await process_referral_reward(session, user.id)
        if bot:
            await announce_to_channel(bot, session, "🧠 تم تأكيد دفعة إنشاء كود جديد بنجاح.")
    elif purpose.startswith("file:"):
        file_id = int(purpose.split(":")[1])
        purchase_repo = PurchaseRepository(session)
        file_repo = CodeFileRepository(session)
        await purchase_repo.create(user.id, "file", file_id, payment.amount)
        await file_repo.increment_downloads(file_id)
        await stats_repo.bump_file_sale(payment.amount)
        await process_referral_reward(session, user.id)
        item = await file_repo.get(file_id)
        if item and bot:
            try:
                await bot.send_document(user.telegram_id, item.file_id, caption=f"✅ {item.title}")
            except Exception:
                pass
            await announce_to_channel(bot, session, f"📦 تم بيع ملف \"{item.title}\" بنجاح.")
    elif purpose.startswith("vip:"):
        plan_id = int(purpose.split(":")[1])
        plan_repo = VipPlanRepository(session)
        plan = await plan_repo.get(plan_id)
        if plan:
            await activate_subscription(session, user.id, plan)
            if bot:
                await announce_to_channel(bot, session, f"👑 اشتراك VIP جديد في باقة {plan.name} تم تفعيله بنجاح.")
