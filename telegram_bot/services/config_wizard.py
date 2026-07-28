"""
معالج أسئلة الإعداد (Configuration Wizard) لمولّد المشاريع بالذكاء الاصطناعي:
يجمع المتغيرات المطلوبة واحدًا تلو الآخر، ويتحقق من صحتها قبل المتابعة.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

BOT_TOKEN_RE = re.compile(r"^\d{6,10}:[A-Za-z0-9_-]{30,45}$")
DATABASE_URL_RE = re.compile(r"^[a-zA-Z0-9+]+://")


@dataclass
class ConfigVariable:
    key: str
    prompt: str
    required: bool
    validator: str  # bot_token / admin_id / api_key / database_url / text


REQUIRED_VARIABLES: list[ConfigVariable] = [
    ConfigVariable("BOT_TOKEN", "🔑 من فضلك أرسل توكن البوت (Bot Token) من BotFather:", True, "bot_token"),
    ConfigVariable("ADMIN_ID", "🆔 من فضلك أرسل معرّف الأدمن (Admin ID) الرقمي:", True, "admin_id"),
]

OPTIONAL_VARIABLES: list[ConfigVariable] = [
    ConfigVariable(
        "DATABASE_URL",
        "🗄️ أرسل رابط قاعدة البيانات (DATABASE_URL) أو أرسل 'تخطي' لاستخدام SQLite الافتراضي:",
        False, "database_url",
    ),
    ConfigVariable(
        "API_KEYS",
        "🔑 أرسل أي مفاتيح API إضافية يحتاجها مشروعك (أو أرسل 'تخطي'):",
        False, "api_key",
    ),
    ConfigVariable(
        "PAYMENT_KEYS",
        "💳 أرسل مفاتيح بوابات الدفع إن وُجدت (أو أرسل 'تخطي'):",
        False, "api_key",
    ),
]


def validate_value(validator: str, value: str) -> tuple[bool, str]:
    value = value.strip()

    if validator == "bot_token":
        if BOT_TOKEN_RE.match(value):
            return True, value
        return False, "⚠️ توكن غير صحيح. الصيغة المتوقعة: 123456789:ABCDEF... أرسل التوكن الصحيح:"

    if validator == "admin_id":
        if value.isdigit() and len(value) >= 5:
            return True, value
        return False, "⚠️ معرّف الأدمن يجب أن يكون رقمًا صحيحًا. أرسل المعرّف الصحيح:"

    if validator == "database_url":
        if value.lower() in ("تخطي", "skip", ""):
            return True, ""
        if DATABASE_URL_RE.match(value):
            return True, value
        return False, "⚠️ صيغة رابط قاعدة البيانات غير صحيحة (مثال: postgresql+asyncpg://user:pass@host/db). حاول مجددًا أو أرسل 'تخطي':"

    if validator == "api_key":
        if value.lower() in ("تخطي", "skip", ""):
            return True, ""
        if len(value) >= 8:
            return True, value
        return False, "⚠️ القيمة قصيرة جدًا لتكون مفتاحًا صالحًا. حاول مجددًا أو أرسل 'تخطي':"

    return True, value


def build_env_content(collected: dict[str, str]) -> str:
    lines = ["# تم إنشاء هذا الملف تلقائيًا بواسطة معالج الإعداد (Configuration Wizard)"]
    for key, value in collected.items():
        if value:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"
