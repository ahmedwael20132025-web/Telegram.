"""
زرع القيم الافتراضية في قاعدة البيانات عند أول تشغيل
"""
from __future__ import annotations

from database.engine import async_session_maker
from database.repository import (
    ButtonRepository,
    PaymentMethodRepository,
    SettingsRepository,
)

DEFAULT_SETTINGS = {
    "bot_name": "بوت إنشاء الأكواد",
    "free_credits_default": "3",
    "code_generation_price": "10",
    "forced_subscription_enabled": "0",
    "referral_enabled": "1",
    "referral_reward_type": "wallet",  # wallet / free_credit
    "referral_reward_value": "5",
    "referral_min_invites": "1",
    "bot_channel_url": "",
    "bot_channel_name": "📢 قناة البوت",
    "bot_channel_visible": "1",
    "bot_channel_chat_id": "",
    "channel_announcements_enabled": "1",
    "default_ai_provider": "google",
    "min_withdraw_amount": "20",
    "auto_backup_enabled": "1",
    "auto_backup_hour": "3",
    "backup_keep_count": "10",
}

DEFAULT_PAYMENT_METHODS = [
    dict(code="stars", name="⭐ Telegram Stars", price=10, currency="STARS",
         instructions="ادفع مباشرة عبر نجوم تيليجرام وسيتم التأكيد تلقائيًا."),
    dict(code="vodafone_cash", name="📱 Vodafone Cash", price=10, currency="EGP",
         instructions="حوّل المبلغ إلى الرقم المحدد ثم أرسل صورة إثبات التحويل."),
]

DEFAULT_BUTTONS = [
    dict(code="generate_code", text="إنشاء كود", emoji="🧠", action_type="feature", target="generate_code", sort_order=1, menu="main"),
    dict(code="project_generator", text="مولّد المشاريع AI", emoji="🧱", action_type="feature", target="project_generator", sort_order=2, menu="main"),
    dict(code="code_files", text="الملفات البرمجية", emoji="📂", action_type="feature", target="code_files", sort_order=3, menu="main"),
    dict(code="vip", text="عضوية VIP", emoji="👑", action_type="feature", target="vip", sort_order=4, menu="main"),
    dict(code="wallet", text="محفظتي", emoji="💰", action_type="feature", target="wallet", sort_order=5, menu="main"),
    dict(code="referral", text="الإحالة", emoji="🎁", action_type="feature", target="referral", sort_order=6, menu="main"),
    dict(code="bot_channel", text="قناة البوت", emoji="📢", action_type="feature", target="bot_channel", sort_order=7, menu="main"),
    dict(code="language", text="اللغة", emoji="🌐", action_type="feature", target="language", sort_order=8, menu="main"),
    dict(code="support", text="الدعم الفني", emoji="🆘", action_type="feature", target="support", sort_order=9, menu="main"),
]


async def seed_defaults() -> None:
    async with async_session_maker() as session:
        settings_repo = SettingsRepository(session)
        for key, value in DEFAULT_SETTINGS.items():
            existing = await settings_repo.get(key, "")
            if not existing:
                await settings_repo.set(key, value)

        methods_repo = PaymentMethodRepository(session)
        existing_methods = await methods_repo.list_all()
        if not existing_methods:
            for method in DEFAULT_PAYMENT_METHODS:
                await methods_repo.create(**method)

        buttons_repo = ButtonRepository(session)
        existing_buttons = await buttons_repo.list_all("main")
        if not existing_buttons:
            for button in DEFAULT_BUTTONS:
                await buttons_repo.create(**button)
