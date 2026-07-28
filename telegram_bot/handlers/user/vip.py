"""
ميزة عضوية VIP - عرض الباقات، الشراء عبر المحفظة/نجوم/دفع يدوي، عرض الحالة والسجل
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import PaymentStatus, WalletOpType
from database.repository import (
    PaymentMethodRepository,
    PaymentRepository,
    UserRepository,
    VipPlanRepository,
    VipSubscriptionRepository,
)
from keyboards.dynamic import simple_back_keyboard
from services.vip_service import get_vip_status, activate_subscription
from states.user_states import VipStates
from utils.helpers import format_money

router = Router(name="vip")


@router.callback_query(F.data == "feat:vip")
async def show_vip_menu(callback: CallbackQuery, session, user) -> None:
    is_vip, sub = await get_vip_status(session, user.id)
    plan_repo = VipPlanRepository(session)
    plans = await plan_repo.list_active()

    status_line = "🚫 لست مشتركًا في VIP حاليًا."
    if is_vip and sub:
        plan = await plan_repo.get(sub.plan_id)
        expiry = "مدى الحياة ♾️" if not sub.expires_at else sub.expires_at.strftime("%Y-%m-%d")
        status_line = f"✅ عضويتك: {plan.badge} {plan.name}\nتنتهي في: {expiry}"

    perks_line = (
        "🎯 <b>مزايا VIP:</b>\n"
        "🧠 إنشاء أكواد بلا حدود (بدون عدّاد)\n"
        "🧱 استخدام مولّد المشاريع بلا حدود\n"
        "📤 رفع وتعديل مشاريعك الخاصة\n"
        "👑 تحميل الملفات الحصرية مجانًا\n"
        "📢 تخطي شرط الاشتراك الإجباري (إن وُجد)"
    )

    rows = [
        [InlineKeyboardButton(
            text=f"{p.badge} {p.name} — {format_money(p.price)}", callback_data=f"vipplan:{p.id}"
        )]
        for p in plans
    ]
    rows.append([InlineKeyboardButton(text="📜 سجل الاشتراكات", callback_data="vip_history")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="nav:main")])

    await callback.message.edit_text(
        f"👑 <b>عضوية VIP</b>\n\n{status_line}\n\n{perks_line}\n\nالباقات المتاحة:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vipplan:"))
async def view_plan(callback: CallbackQuery, session) -> None:
    plan_id = int(callback.data.split(":")[1])
    plan_repo = VipPlanRepository(session)
    plan = await plan_repo.get(plan_id)
    if not plan or not plan.is_active:
        await callback.answer("⚠️ هذه الباقة غير متاحة.", show_alert=True)
        return

    text = (
        f"{plan.badge} <b>{plan.name}</b>\n\n{plan.description}\n\n"
        f"🎯 المزايا:\n{plan.features}\n\n💰 السعر: {format_money(plan.price)}"
    )
    rows = [
        [InlineKeyboardButton(text="💰 الدفع من المحفظة", callback_data=f"vipbuy_wallet:{plan_id}")],
        [InlineKeyboardButton(text="💳 دفع يدوي", callback_data=f"vipbuy_manual:{plan_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="feat:vip")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("vipbuy_wallet:"))
async def buy_with_wallet(callback: CallbackQuery, session, user) -> None:
    plan_id = int(callback.data.split(":")[1])
    plan_repo = VipPlanRepository(session)
    plan = await plan_repo.get(plan_id)
    if not plan:
        await callback.answer("⚠️ الباقة غير متاحة.", show_alert=True)
        return

    if user.wallet_balance < plan.price:
        await callback.answer("❌ رصيدك غير كافٍ. اختر الدفع اليدوي بدلاً من ذلك.", show_alert=True)
        return

    user_repo = UserRepository(session)
    await user_repo.adjust_wallet(user, -plan.price, WalletOpType.purchase, note=f"اشتراك VIP: {plan.name}")
    await activate_subscription(session, user.id, plan)

    from services.announcer import announce_to_channel

    await announce_to_channel(callback.bot, session, f"👑 اشتراك VIP جديد في باقة {plan.name} تم تفعيله بنجاح.")

    await callback.message.edit_text(
        f"✅ تم تفعيل اشتراكك في {plan.badge} {plan.name} بنجاح!",
        reply_markup=simple_back_keyboard(user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vipbuy_manual:"))
async def buy_manual(callback: CallbackQuery, state: FSMContext, session) -> None:
    plan_id = int(callback.data.split(":")[1])
    methods_repo = PaymentMethodRepository(session)
    methods = await methods_repo.list_active()

    if not methods:
        await callback.answer("⚠️ لا توجد طرق دفع مفعّلة.", show_alert=True)
        return

    await state.update_data(plan_id=plan_id)
    rows = [
        [InlineKeyboardButton(text=m.name, callback_data=f"vippay:{m.id}")] for m in methods
    ]
    await callback.message.answer("💳 اختر طريقة الدفع:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("vippay:"))
async def choose_vip_payment(callback: CallbackQuery, state: FSMContext, session, user) -> None:
    method_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    plan_id = data.get("plan_id")

    plan_repo = VipPlanRepository(session)
    plan = await plan_repo.get(plan_id)
    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)

    if not plan or not method:
        await callback.answer("⚠️ حدث خطأ.", show_alert=True)
        return

    await state.update_data(method_id=method_id)

    if method.code == "stars":
        from services.stars_payment import send_stars_invoice

        await send_stars_invoice(
            callback.bot, callback.from_user.id,
            title=f"اشتراك VIP: {plan.name}", description=plan.description or "اشتراك عضوية VIP",
            payload=f"vip:{plan_id}:{user.id}", amount_stars=int(plan.price),
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"{method.instructions}\n\n💰 المبلغ المطلوب: {format_money(plan.price)} {method.currency}"
    )
    await callback.message.answer("📎 أرسل الآن صورة إثبات التحويل أو رقم العملية.")
    await state.set_state(VipStates.waiting_payment_proof)
    await callback.answer()


@router.message(VipStates.waiting_payment_proof)
async def receive_vip_proof(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    plan_id = data.get("plan_id")
    method_id = data.get("method_id")

    plan_repo = VipPlanRepository(session)
    plan = await plan_repo.get(plan_id)
    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)

    if not plan or not method:
        return

    proof_file_id = message.photo[-1].file_id if message.photo else None
    reference = message.caption if message.photo else message.text

    status = PaymentStatus.approved if method.code == "stars" else PaymentStatus.pending
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.create(
        user_id=user.id, method_id=method_id, amount=plan.price, purpose=f"vip:{plan_id}",
        reference=reference, proof_file_id=proof_file_id, status=status,
    )

    if status == PaymentStatus.approved:
        await activate_subscription(session, user.id, plan)
        await message.answer(f"✅ تم تفعيل اشتراكك في {plan.badge} {plan.name} بنجاح!")

        from services.announcer import announce_to_channel

        await announce_to_channel(message.bot, session, f"👑 اشتراك VIP جديد في باقة {plan.name} تم تفعيله بنجاح.")
    else:
        await message.answer("⏳ تم استلام طلبك، سيتم مراجعته من الإدارة قريبًا.")
        for admin_id in await _admin_ids(session):
            try:
                await message.bot.send_message(
                    admin_id,
                    f"👑 طلب اشتراك VIP جديد #{payment.id}\nالمستخدم: {user.telegram_id}\n"
                    f"الباقة: {plan.name}\nالمبلغ: {plan.price}",
                )
            except Exception:
                pass

    await state.clear()


@router.callback_query(F.data == "vip_history")
async def show_vip_history(callback: CallbackQuery, session, user) -> None:
    sub_repo = VipSubscriptionRepository(session)
    plan_repo = VipPlanRepository(session)
    history = await sub_repo.history_for_user(user.id)

    if not history:
        text = "📜 لا يوجد سجل اشتراكات بعد."
    else:
        lines = []
        for sub in history[:10]:
            plan = await plan_repo.get(sub.plan_id)
            plan_name = plan.name if plan else "—"
            expiry = "مدى الحياة" if not sub.expires_at else sub.expires_at.strftime("%Y-%m-%d")
            lines.append(f"• {plan_name} — {sub.status} — ينتهي: {expiry}")
        text = "📜 <b>سجل اشتراكاتك</b>\n\n" + "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=simple_back_keyboard(user.language), parse_mode="HTML")
    await callback.answer()


async def _admin_ids(session) -> list[int]:
    from config import config
    from database.repository import AdminRepository

    admins = await AdminRepository(session).list_all()
    return list({*config.super_admins, *(a.telegram_id for a in admins)})
