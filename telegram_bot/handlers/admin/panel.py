"""
لوحة الأدمن الرئيسية: الدخول، الإحصائيات، الإعدادات، مزود الذكاء الاصطناعي، API Keys، الحظر، السجلات
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import User
from database.repository import (
    AIRequestRepository,
    LogRepository,
    PaymentRepository,
    SettingsRepository,
    StatisticRepository,
    UserRepository,
)
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard, admin_main_menu
from states.admin_states import AdminApiKeyStates, AdminSettingStates
from utils.helpers import format_money

router = Router(name="admin_panel")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def open_admin_panel(message: Message) -> None:
    await message.answer("🛠️ لوحة تحكم الأدمن", reply_markup=admin_main_menu())


@router.callback_query(F.data == "adm:main")
async def back_to_admin_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🛠️ لوحة تحكم الأدمن", reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "adm:stats")
async def show_stats(callback: CallbackQuery, session) -> None:
    stats_repo = StatisticRepository(session)
    user_repo = UserRepository(session)
    ai_repo = AIRequestRepository(session)

    today = await stats_repo.totals(1)
    week = await stats_repo.totals(7)
    month = await stats_repo.totals(30)
    total_users = await user_repo.count_all()
    total_ai_requests = await ai_repo.count_total()

    text = (
        "📊 <b>الإحصائيات</b>\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"🧠 إجمالي طلبات الذكاء الاصطناعي: {total_ai_requests}\n\n"
        f"📅 اليوم: مستخدمون جدد {today['new_users']} | أكواد {today['code_generations']} | "
        f"مبيعات ملفات {today['files_sold']} | أرباح {format_money(today['revenue'])}\n\n"
        f"🗓️ آخر 7 أيام: مستخدمون جدد {week['new_users']} | أكواد {week['code_generations']} | "
        f"مبيعات ملفات {week['files_sold']} | أرباح {format_money(week['revenue'])}\n\n"
        f"📆 آخر 30 يوم: مستخدمون جدد {month['new_users']} | أكواد {month['code_generations']} | "
        f"مبيعات ملفات {month['files_sold']} | أرباح {format_money(month['revenue'])}"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:referrals")
async def show_referral_settings(callback: CallbackQuery, session) -> None:
    settings_repo = SettingsRepository(session)
    enabled = await settings_repo.get_bool("referral_enabled", True)
    reward_type = await settings_repo.get("referral_reward_type", "wallet")
    reward_value = await settings_repo.get_float("referral_reward_value", 5)
    min_invites = await settings_repo.get_int("referral_min_invites", 1)

    text = (
        f"🎁 <b>إعدادات الإحالة</b>\n\n"
        f"الحالة: {'مفعّلة' if enabled else 'متوقفة'}\n"
        f"نوع المكافأة: {reward_type}\n"
        f"قيمة المكافأة: {reward_value}\n"
        f"أقل عدد دعوات: {min_invites}\n\n"
        f"لتعديل القيم استخدم قسم ⚙ الإعدادات."
    )
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل الإحالة", callback_data="admset_toggle:referral_enabled")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:revenue")
async def show_revenue(callback: CallbackQuery, session) -> None:
    payment_repo = PaymentRepository(session)
    total = await payment_repo.sum_approved()
    await callback.message.edit_text(
        f"💰 إجمالي الأرباح المؤكدة: {format_money(total)}", reply_markup=admin_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "adm:logs")
async def show_logs(callback: CallbackQuery, session) -> None:
    log_repo = LogRepository(session)
    logs = await log_repo.recent(15)
    if not logs:
        text = "📈 لا توجد سجلات حتى الآن."
    else:
        lines = [f"[{log.level}] {log.created_at:%Y-%m-%d %H:%M} — {log.message[:150]}" for log in logs]
        text = "📈 <b>آخر السجلات</b>\n\n" + "\n\n".join(lines)
    await callback.message.edit_text(text[:4000], reply_markup=admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


# --------------------------------------------------------------- الإعدادات --
SETTINGS_FIELDS = {
    "bot_name": "اسم البوت",
    "free_credits_default": "عدد مرات الإنشاء المجانية",
    "project_generator_free_default": "عدد مرات مولّد المشاريع المجانية",
    "project_generator_price": "سعر مولّد المشاريع بعد المرات المجانية",
    "code_generation_price": "سعر إنشاء الكود",
    "min_withdraw_amount": "الحد الأدنى للسحب",
    "referral_reward_value": "قيمة مكافأة الإحالة",
    "referral_min_invites": "أقل عدد دعوات مطلوب",
    "bot_channel_url": "رابط قناة البوت",
    "bot_channel_name": "اسم زر قناة البوت",
    "bot_channel_chat_id": "معرف قناة البوت (Chat ID) للإعلانات التلقائية",
    "support_username": "معرف الدعم الفني (بدون @)",
    "auto_backup_hour": "ساعة النسخ الاحتياطي التلقائي (0-23)",
}


@router.callback_query(F.data == "adm:settings")
async def show_settings(callback: CallbackQuery, session) -> None:
    settings_repo = SettingsRepository(session)
    rows = []
    for key, label in SETTINGS_FIELDS.items():
        value = await settings_repo.get(key, "")
        rows.append([InlineKeyboardButton(text=f"{label}: {value or '—'}", callback_data=f"admset:{key}")])
    rows.append([InlineKeyboardButton(text="🔁 تبديل الاشتراك الإجباري", callback_data="admset_toggle:forced_subscription_enabled")])
    rows.append([InlineKeyboardButton(text="🔁 تبديل نظام الإحالة", callback_data="admset_toggle:referral_enabled")])
    rows.append([InlineKeyboardButton(text="🔁 تبديل النسخ الاحتياطي التلقائي", callback_data="admset_toggle:auto_backup_enabled")])
    rows.append([InlineKeyboardButton(text="🔁 تبديل الإعلان التلقائي في القناة", callback_data="admset_toggle:channel_announcements_enabled")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])
    await callback.message.edit_text("⚙ إعدادات البوت", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("admset_toggle:"))
async def toggle_setting(callback: CallbackQuery, session) -> None:
    key = callback.data.split(":", 1)[1]
    settings_repo = SettingsRepository(session)
    current = await settings_repo.get_bool(key, False)
    await settings_repo.set(key, "0" if current else "1")
    await callback.answer("✅ تم التحديث")
    await show_settings(callback, session)


@router.callback_query(F.data.startswith("admset:"))
async def ask_setting_value(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    await state.update_data(setting_key=key)
    await state.set_state(AdminSettingStates.waiting_value)
    await callback.message.answer(f"✍️ أرسل القيمة الجديدة لـ: {SETTINGS_FIELDS.get(key, key)}")
    await callback.answer()


@router.message(AdminSettingStates.waiting_value)
async def save_setting_value(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    key = data.get("setting_key")
    if not key:
        return
    settings_repo = SettingsRepository(session)
    await settings_repo.set(key, message.text.strip())
    await message.answer("✅ تم الحفظ بنجاح.")
    await state.clear()


# ------------------------------------------------------- مزود الذكاء الاصطناعي
@router.callback_query(F.data == "adm:ai_provider")
async def show_ai_provider(callback: CallbackQuery, session) -> None:
    settings_repo = SettingsRepository(session)
    current = await settings_repo.get("default_ai_provider", "claude")
    rows = [
        [InlineKeyboardButton(
            text=("✅ " if current == "claude" else "") + "Claude API", callback_data="setai:claude"
        )],
        [InlineKeyboardButton(
            text=("✅ " if current == "openai" else "") + "OpenAI API", callback_data="setai:openai"
        )],
        [InlineKeyboardButton(
            text=("✅ " if current == "google" else "") + "Google Gemini API (مجاني)", callback_data="setai:google"
        )],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]
    await callback.message.edit_text("🤖 اختر مزود الذكاء الاصطناعي:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("setai:"))
async def set_ai_provider(callback: CallbackQuery, session) -> None:
    provider = callback.data.split(":")[1]
    settings_repo = SettingsRepository(session)
    await settings_repo.set("default_ai_provider", provider)
    await callback.answer("✅ تم التحديث")
    await show_ai_provider(callback, session)


@router.callback_query(F.data == "adm:api_keys")
async def show_api_keys_menu(callback: CallbackQuery) -> None:
    rows = [
        [InlineKeyboardButton(text="🔑 تحديث Claude API Key", callback_data="apikey:claude")],
        [InlineKeyboardButton(text="🔑 تحديث OpenAI API Key", callback_data="apikey:openai")],
        [InlineKeyboardButton(text="🔑 تحديث Google (Gemini) API Key", callback_data="apikey:google")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")],
    ]
    await callback.message.edit_text(
        "🔑 مفاتيح API محفوظة في ملف .env على السيرفر لأسباب أمنية.\n"
        "لتحديثها أرسل القيمة الجديدة، وسيتم حفظها بشكل مؤقت في هذه الجلسة "
        "(يُنصح بتحديث ملف .env وإعادة تشغيل البوت للتأكيد الدائم).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("apikey:"))
async def ask_api_key(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":")[1]
    state_map = {
        "claude": AdminApiKeyStates.waiting_claude_key,
        "openai": AdminApiKeyStates.waiting_openai_key,
        "google": AdminApiKeyStates.waiting_google_key,
    }
    await state.set_state(state_map[provider])
    await callback.message.answer(f"✍️ أرسل مفتاح {provider} الجديد:")
    await callback.answer()


@router.message(AdminApiKeyStates.waiting_claude_key)
async def save_claude_key(message: Message, state: FSMContext) -> None:
    import config as config_module

    config_module.config.__dict__["claude_api_key"] = message.text.strip()
    await message.answer("✅ تم تحديث مفتاح Claude لهذه الجلسة.")
    await state.clear()


@router.message(AdminApiKeyStates.waiting_openai_key)
async def save_openai_key(message: Message, state: FSMContext) -> None:
    import config as config_module

    config_module.config.__dict__["openai_api_key"] = message.text.strip()
    await message.answer("✅ تم تحديث مفتاح OpenAI لهذه الجلسة.")
    await state.clear()


@router.message(AdminApiKeyStates.waiting_google_key)
async def save_google_key(message: Message, state: FSMContext) -> None:
    import config as config_module

    config_module.config.__dict__["google_api_key"] = message.text.strip()
    await message.answer("✅ تم تحديث مفتاح Google (Gemini) لهذه الجلسة.")
    await state.clear()
