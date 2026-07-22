import logging
import time

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import config
import db

logger = logging.getLogger(__name__)
router = Router()

USERS_PAGE_SIZE = 8


# ---------------- تأمين: الأدمن بس ----------------
def is_admin(user_id: int) -> bool:
    return config.ADMIN_TELEGRAM_ID != 0 and user_id == config.ADMIN_TELEGRAM_ID


# ---------------- الحالات (FSM) ----------------
class AdminStates(StatesGroup):
    edit_welcome = State()
    edit_channel_button_text = State()
    edit_channel_url = State()
    edit_price_video = State()
    edit_price_stars = State()
    edit_currency_label = State()
    edit_force_sub_channel = State()
    edit_force_sub_channel_url = State()
    add_payment_name = State()
    add_payment_details = State()
    broadcast_text = State()
    add_free_user = State()


# ---------------- لوحات المفاتيح ----------------
def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="adm_stats")],
            [InlineKeyboardButton(text="⚙️ الإعدادات العامة", callback_data="adm_settings")],
            [InlineKeyboardButton(text="💰 أسعار الفيديو", callback_data="adm_pricing")],
            [InlineKeyboardButton(text="🔒 الاشتراك الإجباري", callback_data="adm_forcesub")],
            [InlineKeyboardButton(text="💳 طرق الدفع", callback_data="adm_paymethods")],
            [InlineKeyboardButton(text="📋 طلبات الشحن", callback_data="adm_topups")],
            [InlineKeyboardButton(text="🆓 المستخدمين المجانيين", callback_data="adm_free_users")],
            [InlineKeyboardButton(text="👥 الأعضاء", callback_data="adm_users_0")],
            [InlineKeyboardButton(text="📢 رسالة جماعية", callback_data="adm_broadcast")],
        ]
    )


def back_kb(target="adm_home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data=target)]]
    )


# ---------------- دخول لوحة التحكم ----------------
@router.message(Command("admin"))
async def admin_entry(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return  # مش هيرد خالص لو مش الأدمن، عشان محدش يعرف إن فيه لوحة تحكم أصلاً
    await state.clear()
    await message.answer("🛠 لوحة تحكم البوت", reply_markup=admin_main_kb())


@router.callback_query(F.data == "adm_home")
async def adm_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("🛠 لوحة تحكم البوت", reply_markup=admin_main_kb())


# ---------------- الإحصائيات ----------------
@router.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    total = db.count_users()
    pending = db.count_pending_topup_requests()
    free_count = len(db.get_free_users())
    text = (
        "📊 إحصائيات البوت\n\n"
        f"👥 إجمالي الأعضاء: {total}\n"
        f"⏳ طلبات شحن في الانتظار: {pending}\n"
        f"🆓 مستخدمين مجانيين: {free_count}\n"
    )
    await callback.message.edit_text(text, reply_markup=back_kb())


# ---------------- الإعدادات العامة ----------------
def settings_view_text() -> str:
    s = db.get_all_settings()
    return (
        "⚙️ الإعدادات الحالية:\n\n"
        f"📝 نص الترحيب:\n{s.get('welcome_text','')}\n\n"
        f"🔘 نص زر القناة: {s.get('channel_button_text','')}\n"
        f"🔗 رابط القناة: {s.get('channel_url','')}\n"
    )


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ تعديل نص الترحيب", callback_data="adm_set_welcome")],
            [InlineKeyboardButton(text="✏️ تعديل نص زر القناة", callback_data="adm_set_btntext")],
            [InlineKeyboardButton(text="✏️ تعديل رابط القناة", callback_data="adm_set_url")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")],
        ]
    )


@router.callback_query(F.data == "adm_settings")
async def adm_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(settings_view_text(), reply_markup=settings_kb())


async def _ask_for_text(callback: CallbackQuery, state: FSMContext, new_state, prompt: str, back_target="adm_settings"):
    await state.set_state(new_state)
    await callback.message.edit_text(prompt, reply_markup=back_kb(back_target))


@router.callback_query(F.data == "adm_set_welcome")
async def adm_set_welcome(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(callback, state, AdminStates.edit_welcome, "📝 ابعت نص الترحيب الجديد:")


@router.callback_query(F.data == "adm_set_btntext")
async def adm_set_btntext(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(callback, state, AdminStates.edit_channel_button_text, "🔘 ابعت نص زرار القناة الجديد:")


@router.callback_query(F.data == "adm_set_url")
async def adm_set_url(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(callback, state, AdminStates.edit_channel_url, "🔗 ابعت رابط القناة الجديد (مثال: https://t.me/mychannel):")


@router.message(AdminStates.edit_welcome, F.text)
async def save_welcome(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("welcome_text", message.text)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=settings_kb())


@router.message(AdminStates.edit_channel_button_text, F.text)
async def save_btntext(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("channel_button_text", message.text)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=settings_kb())


@router.message(AdminStates.edit_channel_url, F.text)
async def save_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("⚠️ الرابط لازم يبدأ بـ https:// حاول تاني:")
        return
    db.set_setting("channel_url", url)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=settings_kb())


# ---------------- أسعار الفيديو ----------------
def pricing_view_text() -> str:
    price = db.get_price_per_video()
    stars = db.get_price_per_video_stars()
    currency = db.get_setting("currency_label", "جنيه")
    return (
        "💰 أسعار الفيديو الحالية:\n\n"
        f"💵 سعر الفيديو (دفع يدوي): {price:g} {currency}\n"
        f"⭐ سعر الفيديو (نجوم تليجرام): {stars} نجمة\n"
        f"🏷 اسم العملة المعروض: {currency}\n"
    )


def pricing_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ تعديل سعر الفيديو (يدوي)", callback_data="adm_set_price_video")],
            [InlineKeyboardButton(text="✏️ تعديل سعر الفيديو (نجوم)", callback_data="adm_set_price_stars")],
            [InlineKeyboardButton(text="✏️ تعديل اسم العملة", callback_data="adm_set_currency")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")],
        ]
    )


@router.callback_query(F.data == "adm_pricing")
async def adm_pricing(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(pricing_view_text(), reply_markup=pricing_kb())


@router.callback_query(F.data == "adm_set_price_video")
async def adm_set_price_video(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(
        callback, state, AdminStates.edit_price_video,
        "💵 ابعت سعر الفيديو الواحد (رقم، بالعملة المحلية):",
        back_target="adm_pricing",
    )


@router.message(AdminStates.edit_price_video, F.text)
async def save_price_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip().replace(",", ".")
    try:
        value = float(txt)
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لازم تبعت رقم أكبر من صفر، حاول تاني:")
        return
    db.set_setting("price_per_video", txt)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=pricing_kb())


@router.callback_query(F.data == "adm_set_price_stars")
async def adm_set_price_stars(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(
        callback, state, AdminStates.edit_price_stars,
        "⭐ ابعت سعر الفيديو الواحد بالنجوم (رقم صحيح):",
        back_target="adm_pricing",
    )


@router.message(AdminStates.edit_price_stars, F.text)
async def save_price_stars(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt.isdigit() or int(txt) <= 0:
        await message.answer("⚠️ لازم تبعت رقم صحيح أكبر من صفر، حاول تاني:")
        return
    db.set_setting("price_per_video_stars", txt)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=pricing_kb())


@router.callback_query(F.data == "adm_set_currency")
async def adm_set_currency(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _ask_for_text(
        callback, state, AdminStates.edit_currency_label,
        "🏷 ابعت اسم العملة اللي هيظهر للمستخدمين (مثال: جنيه، دولار، ريال):",
        back_target="adm_pricing",
    )


@router.message(AdminStates.edit_currency_label, F.text)
async def save_currency_label(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("currency_label", message.text.strip())
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=pricing_kb())


# ---------------- الاشتراك الإجباري ----------------
def forcesub_view_text() -> str:
    s = db.get_all_settings()
    status = "🟢 مفعّل" if s.get("force_sub_enabled") == "1" else "🔴 موقوف"
    return (
        "🔒 الاشتراك الإجباري (لازم المستخدم ينضم لقناة عشان يستخدم البوت)\n\n"
        f"الحالة: {status}\n"
        f"يوزر نيم القناة: {s.get('force_sub_channel') or '(مش محدد)'}\n"
        f"رابط القناة: {s.get('force_sub_channel_url') or '(مش محدد)'}\n\n"
        "⚠️ لازم تعمل البوت أدمن في القناة عشان الميزة دي تشتغل صح."
    )


def forcesub_kb() -> InlineKeyboardMarkup:
    enabled = db.get_setting("force_sub_enabled") == "1"
    toggle_text = "🔴 إيقاف الاشتراك الإجباري" if enabled else "🟢 تفعيل الاشتراك الإجباري"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="adm_forcesub_toggle")],
            [InlineKeyboardButton(text="✏️ تعديل يوزر نيم القناة", callback_data="adm_forcesub_channel")],
            [InlineKeyboardButton(text="✏️ تعديل رابط القناة", callback_data="adm_forcesub_url")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")],
        ]
    )


@router.callback_query(F.data == "adm_forcesub")
async def adm_forcesub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(forcesub_view_text(), reply_markup=forcesub_kb())


@router.callback_query(F.data == "adm_forcesub_toggle")
async def adm_forcesub_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    current = db.get_setting("force_sub_enabled") == "1"
    db.set_setting("force_sub_enabled", "0" if current else "1")
    await callback.message.edit_text(forcesub_view_text(), reply_markup=forcesub_kb())


@router.callback_query(F.data == "adm_forcesub_channel")
async def adm_forcesub_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.edit_force_sub_channel)
    await callback.message.edit_text(
        "✏️ ابعت يوزر نيم القناة بالشكل @channel_username:",
        reply_markup=back_kb("adm_forcesub"),
    )


@router.message(AdminStates.edit_force_sub_channel, F.text)
async def save_forcesub_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    val = message.text.strip()
    if not val.startswith("@"):
        await message.answer("⚠️ لازم يبدأ بـ @ حاول تاني:")
        return
    db.set_setting("force_sub_channel", val)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=forcesub_kb())


@router.callback_query(F.data == "adm_forcesub_url")
async def adm_forcesub_url(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.edit_force_sub_channel_url)
    await callback.message.edit_text(
        "✏️ ابعت رابط القناة (مثال: https://t.me/mychannel):",
        reply_markup=back_kb("adm_forcesub"),
    )


@router.message(AdminStates.edit_force_sub_channel_url, F.text)
async def save_forcesub_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("⚠️ الرابط لازم يبدأ بـ https:// حاول تاني:")
        return
    db.set_setting("force_sub_channel_url", url)
    await state.clear()
    await message.answer("✅ تم التحديث", reply_markup=forcesub_kb())


# ---------------- طرق الدفع ----------------
def paymethods_kb() -> InlineKeyboardMarkup:
    methods = db.get_all_payment_methods()
    rows = []
    for m in methods:
        status_icon = "🟢" if m["active"] else "🔴"
        rows.append([
            InlineKeyboardButton(text=f"{status_icon} {m['name']}", callback_data=f"adm_pm_view_{m['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ إضافة طريقة دفع جديدة", callback_data="adm_pm_add")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "adm_paymethods")
async def adm_paymethods(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    methods = db.get_all_payment_methods()
    text = "💳 طرق الدفع الحالية:" if methods else "💳 مفيش طرق دفع مضافة لسه."
    await callback.message.edit_text(text, reply_markup=paymethods_kb())


@router.callback_query(F.data == "adm_pm_add")
async def adm_pm_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.add_payment_name)
    await callback.message.edit_text(
        "✏️ ابعت اسم طريقة الدفع (مثال: فودافون كاش):",
        reply_markup=back_kb("adm_paymethods"),
    )


@router.message(AdminStates.add_payment_name, F.text)
async def add_payment_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(pm_name=message.text.strip())
    await state.set_state(AdminStates.add_payment_details)
    await message.answer("✏️ دلوقتي ابعت تفاصيل التحويل (رقم المحفظة أو التعليمات):")


@router.message(AdminStates.add_payment_details, F.text)
async def add_payment_details(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    name = data.get("pm_name", "طريقة دفع")
    db.add_payment_method(name, message.text.strip())
    await state.clear()
    await message.answer("✅ تمت إضافة طريقة الدفع", reply_markup=paymethods_kb())


@router.callback_query(F.data.startswith("adm_pm_view_"))
async def adm_pm_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    method_id = int(callback.data.split("_")[-1])
    methods = {m["id"]: m for m in db.get_all_payment_methods()}
    m = methods.get(method_id)
    if not m:
        await callback.answer("الطريقة دي مش موجودة", show_alert=True)
        return
    status = "🟢 مفعّلة" if m["active"] else "🔴 موقوفة"
    text = f"💳 {m['name']}\n\n{m['details']}\n\nالحالة: {status}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⏸ إيقاف" if m["active"] else "▶️ تفعيل",
                callback_data=f"adm_pm_toggle_{method_id}",
            )],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"adm_pm_delete_{method_id}")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_paymethods")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm_pm_toggle_"))
async def adm_pm_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    method_id = int(callback.data.split("_")[-1])
    methods = {m["id"]: m for m in db.get_all_payment_methods()}
    m = methods.get(method_id)
    if m:
        db.toggle_payment_method(method_id, 0 if m["active"] else 1)
    await callback.message.edit_text("💳 طرق الدفع الحالية:", reply_markup=paymethods_kb())


@router.callback_query(F.data.startswith("adm_pm_delete_"))
async def adm_pm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    method_id = int(callback.data.split("_")[-1])
    db.delete_payment_method(method_id)
    await callback.answer("تم الحذف 🗑")
    await callback.message.edit_text("💳 طرق الدفع الحالية:", reply_markup=paymethods_kb())


# ---------------- طلبات شحن الرصيد ----------------
def topup_review_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ قبول", callback_data=f"adm_topup_ok_{req_id}"),
                InlineKeyboardButton(text="❌ رفض", callback_data=f"adm_topup_no_{req_id}"),
            ]
        ]
    )


@router.callback_query(F.data == "adm_topups")
async def adm_topups(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    pending = db.get_pending_topup_requests()
    if not pending:
        await callback.message.edit_text("📋 مفيش طلبات شحن معلقة حالياً 🎉", reply_markup=back_kb())
        return
    await callback.message.edit_text(f"📋 فيه {len(pending)} طلب معلق، هبعتهملك تحت:", reply_markup=back_kb())
    for r in pending:
        caption = (
            f"👤 المستخدم: @{r['username'] or r['telegram_id']}\n"
            f"💳 الطريقة: {r['method_name']}\n"
            f"🔢 الكمية: {r['quantity']} فيديو\n"
            f"💵 المبلغ: {r['total_price_display']}"
        )
        try:
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=r["proof_file_id"],
                caption=caption,
                reply_markup=topup_review_kb(r["id"]),
            )
        except Exception as e:
            logger.warning(f"failed to show topup request {r['id']}: {e}")


@router.callback_query(F.data.startswith("adm_topup_ok_"))
async def adm_topup_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    req_id = int(callback.data.split("_")[-1])
    result = db.approve_topup_request(req_id)
    if result:
        telegram_id, quantity = result
        try:
            new_balance = db.get_credits(telegram_id)
            await bot.send_message(
                telegram_id,
                f"✅ تم شحن رصيدك بنجاح!\nتم إضافة {quantity} فيديو.\nرصيدك الحالي: {new_balance} فيديو.",
            )
        except Exception as e:
            logger.warning(f"failed to notify user {telegram_id}: {e}")
        try:
            await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n✅ تم القبول")
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await callback.answer("الطلب ده اتعامل معاه قبل كده", show_alert=True)


@router.callback_query(F.data.startswith("adm_topup_no_"))
async def adm_topup_reject(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    req_id = int(callback.data.split("_")[-1])
    telegram_id = db.reject_topup_request(req_id)
    if telegram_id:
        try:
            await bot.send_message(
                telegram_id,
                "❌ للأسف تم رفض إيصال الدفع، تأكد من البيانات وحاول تاني أو تواصل مع الدعم.",
            )
        except Exception as e:
            logger.warning(f"failed to notify user {telegram_id}: {e}")
        try:
            await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n❌ تم الرفض")
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await callback.answer("الطلب ده اتعامل معاه قبل كده", show_alert=True)


# ---------------- المستخدمين المجانيين ----------------
def free_users_kb() -> InlineKeyboardMarkup:
    users = db.get_free_users()
    rows = []
    for u in users:
        rows.append([InlineKeyboardButton(
            text=f"❌ إزالة @{u['username'] or u['telegram_id']}",
            callback_data=f"adm_free_del_{u['telegram_id']}",
        )])
    rows.append([InlineKeyboardButton(text="➕ إضافة مستخدم مجاني", callback_data="adm_free_add")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "adm_free_users")
async def adm_free_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = db.get_free_users()
    text = "🆓 المستخدمين المجانيين:" if users else "🆓 مفيش مستخدمين مجانيين مضافين لسه."
    await callback.message.edit_text(text, reply_markup=free_users_kb())


@router.callback_query(F.data == "adm_free_add")
async def adm_free_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.add_free_user)
    await callback.message.edit_text(
        "✏️ ابعت آيدي المستخدم على تليجرام (رقم فقط).\n"
        "تقدر تعرف آيدي أي حد لو بعتلك أي رسالة، أو خليه يبعت رسالة لبوت @userinfobot ويبعتلك الآيدي.",
        reply_markup=back_kb("adm_free_users"),
    )


@router.message(AdminStates.add_free_user, F.text)
async def save_free_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("⚠️ لازم تبعت آيدي رقمي بس، حاول تاني:")
        return
    telegram_id = int(txt)
    user = db.get_user(telegram_id)
    username = user["username"] if user else ""
    db.add_free_user(telegram_id, username)
    await state.clear()
    await message.answer("✅ تمت الإضافة للمستخدمين المجانيين", reply_markup=free_users_kb())


@router.callback_query(F.data.startswith("adm_free_del_"))
async def adm_free_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    telegram_id = int(callback.data.split("_")[-1])
    db.remove_free_user(telegram_id)
    await callback.answer("تمت الإزالة")
    users = db.get_free_users()
    text = "🆓 المستخدمين المجانيين:" if users else "🆓 مفيش مستخدمين مجانيين مضافين لسه."
    await callback.message.edit_text(text, reply_markup=free_users_kb())


# ---------------- الأعضاء ----------------
def users_page_kb(offset: int, has_more: bool) -> InlineKeyboardMarkup:
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"adm_users_{max(0, offset - USERS_PAGE_SIZE)}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="التالي ➡️", callback_data=f"adm_users_{offset + USERS_PAGE_SIZE}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("adm_users_"))
async def adm_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    offset = int(callback.data.split("_")[-1])
    users = db.get_users_page(offset, USERS_PAGE_SIZE)
    total = db.count_users()
    if not users:
        await callback.message.edit_text("👥 مفيش أعضاء لسه.", reply_markup=back_kb())
        return

    free_ids = {u["telegram_id"] for u in db.get_free_users()}
    lines = [f"👥 الأعضاء ({total} إجمالي) — عرض {offset + 1}-{offset + len(users)}:\n"]
    for u in users:
        tag = " 🆓" if u["telegram_id"] in free_ids else ""
        lines.append(f"• @{u['username'] or u['telegram_id']} — رصيد: {u['credits']}{tag}")
    text = "\n".join(lines)
    has_more = (offset + USERS_PAGE_SIZE) < total
    await callback.message.edit_text(text, reply_markup=users_page_kb(offset, has_more))


# ---------------- رسالة جماعية ----------------
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text(
        "📢 ابعت نص الرسالة اللي عايز ترسلها لكل الأعضاء:",
        reply_markup=back_kb(),
    )


@router.message(AdminStates.broadcast_text, F.text)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    text = message.text
    ids = db.get_all_user_ids()
    sent, failed = 0, 0
    status_msg = await message.answer(f"⏳ جاري الإرسال لـ {len(ids)} عضو...")
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(f"✅ تم الإرسال\nنجح: {sent} | فشل: {failed}")
    await message.answer("🛠 لوحة تحكم البوت", reply_markup=admin_main_kb())
