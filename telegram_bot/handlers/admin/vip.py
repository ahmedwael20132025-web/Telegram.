"""
لوحة الأدمن: إدارة باقات VIP والإحصائيات
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import VipDuration
from database.repository import VipPlanRepository, VipSubscriptionRepository
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard
from states.admin_states import AdminVipStates
from utils.helpers import format_money, is_valid_amount

router = Router(name="admin_vip")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

DURATION_LABELS = {
    VipDuration.weekly: "أسبوعي",
    VipDuration.monthly: "شهري",
    VipDuration.quarterly: "ربع سنوي",
    VipDuration.yearly: "سنوي",
    VipDuration.lifetime: "مدى الحياة",
}


@router.callback_query(F.data == "adm:pricing")
async def pricing_menu(callback: CallbackQuery) -> None:
    rows = [
        [InlineKeyboardButton(text="👑 باقات VIP", callback_data="adm:vip_plans")],
        [InlineKeyboardButton(text="🎟️ الكوبونات", callback_data="adm:coupons")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]
    await callback.message.edit_text("⭐ الأسعار والكوبونات", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:vip_plans")
async def list_vip_plans(callback: CallbackQuery, session) -> None:
    repo = VipPlanRepository(session)
    plans = await repo.list_all()
    sub_repo = VipSubscriptionRepository(session)
    active_count = await sub_repo.count_active()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if p.is_active else '🚫'} {p.badge} {p.name} — {format_money(p.price)}",
            callback_data=f"vipplan_adm:{p.id}",
        )]
        for p in plans
    ]
    rows.append([InlineKeyboardButton(text="➕ إنشاء باقة جديدة", callback_data="vipplan_new")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:pricing")])

    await callback.message.edit_text(
        f"👑 <b>باقات VIP</b>\n\nإجمالي المشتركين النشطين: {active_count}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "vipplan_new")
async def create_plan_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل اسم الباقة:")
    await state.set_state(AdminVipStates.waiting_name)
    await callback.answer()


@router.message(AdminVipStates.waiting_name)
async def create_plan_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await message.answer("😀 أرسل الشارة (Badge) المرافقة للباقة، مثال: 💎")
    await state.set_state(AdminVipStates.waiting_badge)


@router.message(AdminVipStates.waiting_badge)
async def create_plan_badge(message: Message, state: FSMContext) -> None:
    await state.update_data(badge=message.text.strip())
    await message.answer("📝 أرسل وصف الباقة:")
    await state.set_state(AdminVipStates.waiting_description)


@router.message(AdminVipStates.waiting_description)
async def create_plan_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await message.answer("🎯 أرسل قائمة المزايا (سطر لكل ميزة):")
    await state.set_state(AdminVipStates.waiting_features)


@router.message(AdminVipStates.waiting_features)
async def create_plan_features(message: Message, state: FSMContext) -> None:
    await state.update_data(features=message.text.strip())
    await message.answer("💰 أرسل سعر الباقة:")
    await state.set_state(AdminVipStates.waiting_price)


@router.message(AdminVipStates.waiting_price)
async def create_plan_price(message: Message, state: FSMContext) -> None:
    if not is_valid_amount(message.text):
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return
    await state.update_data(price=float(message.text.strip()))

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"vipdur:{key.value}")]
        for key, label in DURATION_LABELS.items()
    ]
    await message.answer("⏳ اختر مدة الاشتراك:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(AdminVipStates.waiting_duration)


@router.callback_query(AdminVipStates.waiting_duration, F.data.startswith("vipdur:"))
async def create_plan_duration(callback: CallbackQuery, state: FSMContext, session) -> None:
    duration = callback.data.split(":")[1]
    data = await state.get_data()

    repo = VipPlanRepository(session)
    all_plans = await repo.list_all()
    plan = await repo.create(
        name=data["name"], badge=data["badge"], description=data["description"],
        features=data["features"], price=data["price"], duration=duration,
        sort_order=len(all_plans),
    )

    await callback.message.answer(f"✅ تم إنشاء باقة {plan.badge} {plan.name} بنجاح.", reply_markup=admin_back_keyboard("adm:vip_plans"))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("vipplan_adm:"))
async def manage_plan(callback: CallbackQuery, session) -> None:
    plan_id = int(callback.data.split(":")[1])
    repo = VipPlanRepository(session)
    plan = await repo.get(plan_id)
    if not plan:
        await callback.answer("⚠️ الباقة غير موجودة.", show_alert=True)
        return

    text = (
        f"{plan.badge} <b>{plan.name}</b>\n\n{plan.description}\n\n"
        f"🎯 {plan.features}\n\n💰 {format_money(plan.price)} | ⏳ {DURATION_LABELS.get(plan.duration, plan.duration)}\n"
        f"الحالة: {'مفعّلة' if plan.is_active else 'متوقفة'}"
    )
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"vipplan_toggle:{plan_id}")],
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"vipplan_delete:{plan_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:vip_plans")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("vipplan_toggle:"))
async def toggle_plan(callback: CallbackQuery, session) -> None:
    plan_id = int(callback.data.split(":")[1])
    repo = VipPlanRepository(session)
    await repo.toggle(plan_id)
    await callback.answer("✅ تم التحديث")
    await manage_plan(callback, session)


@router.callback_query(F.data.startswith("vipplan_delete:"))
async def delete_plan(callback: CallbackQuery, session) -> None:
    plan_id = int(callback.data.split(":")[1])
    repo = VipPlanRepository(session)
    await repo.delete(plan_id)
    await callback.answer("🗑️ تم الحذف")
    await list_vip_plans(callback, session)
