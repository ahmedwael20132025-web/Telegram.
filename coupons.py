"""
لوحة الأدمن: إدارة الكوبونات
"""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import CouponType
from database.repository import CouponRepository
from filters.admin_filter import IsAdmin
from states.admin_states import AdminCouponStates
from utils.helpers import is_valid_amount

router = Router(name="admin_coupons")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:coupons")
async def list_coupons(callback: CallbackQuery, session) -> None:
    repo = CouponRepository(session)
    coupons = await repo.list_all()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if c.is_active else '🚫'} {c.code} ({c.used_count}/{c.max_uses})",
            callback_data=f"coupon_adm:{c.id}",
        )]
        for c in coupons[:15]
    ]
    rows.append([InlineKeyboardButton(text="➕ إنشاء كوبون", callback_data="coupon_new")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:pricing")])

    await callback.message.edit_text("🎟️ الكوبونات", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "coupon_new")
async def create_coupon_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل كود الكوبون:")
    await state.set_state(AdminCouponStates.waiting_code)
    await callback.answer()


@router.message(AdminCouponStates.waiting_code)
async def create_coupon_code(message: Message, state: FSMContext, session) -> None:
    code = message.text.strip().upper()
    repo = CouponRepository(session)
    if await repo.get_by_code(code):
        await message.answer("⚠️ هذا الكود مستخدم بالفعل.")
        return
    await state.update_data(code=code)

    rows = [
        [InlineKeyboardButton(text="نسبة %", callback_data="couptype:percent")],
        [InlineKeyboardButton(text="مبلغ ثابت", callback_data="couptype:fixed")],
    ]
    await message.answer("اختر نوع الخصم:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(AdminCouponStates.waiting_type)


@router.callback_query(AdminCouponStates.waiting_type, F.data.startswith("couptype:"))
async def choose_coupon_type(callback: CallbackQuery, state: FSMContext) -> None:
    coupon_type = callback.data.split(":")[1]
    await state.update_data(coupon_type=coupon_type)
    await callback.message.answer("💰 أرسل قيمة الخصم:")
    await state.set_state(AdminCouponStates.waiting_value)
    await callback.answer()


@router.message(AdminCouponStates.waiting_value)
async def coupon_value(message: Message, state: FSMContext) -> None:
    if not is_valid_amount(message.text):
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return
    await state.update_data(value=float(message.text.strip()))
    await message.answer("🔢 أرسل الحد الأقصى لعدد مرات الاستخدام:")
    await state.set_state(AdminCouponStates.waiting_max_uses)


@router.message(AdminCouponStates.waiting_max_uses)
async def coupon_max_uses(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return
    await state.update_data(max_uses=int(message.text.strip()))
    await message.answer("📅 أرسل عدد أيام صلاحية الكوبون (أو أرسل 0 لعدم انتهاء الصلاحية):")
    await state.set_state(AdminCouponStates.waiting_expiry)


@router.message(AdminCouponStates.waiting_expiry)
async def coupon_expiry(message: Message, state: FSMContext, session) -> None:
    if not message.text.strip().isdigit():
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return

    days = int(message.text.strip())
    expires_at = datetime.utcnow() + timedelta(days=days) if days > 0 else None

    data = await state.get_data()
    repo = CouponRepository(session)
    coupon = await repo.create(
        code=data["code"], coupon_type=data["coupon_type"], value=data["value"],
        max_uses=data["max_uses"], expires_at=expires_at, is_public=True,
    )
    await message.answer(f"✅ تم إنشاء الكوبون {coupon.code} بنجاح.")
    await state.clear()


@router.callback_query(F.data.startswith("coupon_adm:"))
async def manage_coupon(callback: CallbackQuery, session) -> None:
    coupon_id = int(callback.data.split(":")[1])
    repo = CouponRepository(session)
    coupons = await repo.list_all()
    coupon = next((c for c in coupons if c.id == coupon_id), None)
    if not coupon:
        await callback.answer("⚠️ الكوبون غير موجود.", show_alert=True)
        return

    value_display = f"{coupon.value}%" if coupon.coupon_type == CouponType.percent else str(coupon.value)
    text = (
        f"🎟️ <b>{coupon.code}</b>\nالخصم: {value_display}\n"
        f"الاستخدام: {coupon.used_count}/{coupon.max_uses}\n"
        f"الحالة: {'مفعّل' if coupon.is_active else 'متوقف'}"
    )
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"coupon_toggle:{coupon_id}")],
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"coupon_delete:{coupon_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:coupons")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("coupon_toggle:"))
async def toggle_coupon(callback: CallbackQuery, session) -> None:
    coupon_id = int(callback.data.split(":")[1])
    repo = CouponRepository(session)
    await repo.toggle(coupon_id)
    await callback.answer("✅ تم التحديث")
    await manage_coupon(callback, session)


@router.callback_query(F.data.startswith("coupon_delete:"))
async def delete_coupon(callback: CallbackQuery, session) -> None:
    coupon_id = int(callback.data.split(":")[1])
    repo = CouponRepository(session)
    await repo.delete(coupon_id)
    await callback.answer("🗑️ تم الحذف")
    await list_coupons(callback, session)
