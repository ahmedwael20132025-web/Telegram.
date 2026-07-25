"""
نظام تعدد اللغات - النصوص الأساسية من الملفات، مع إمكانية التخصيص من قاعدة البيانات
(مفتاح الإعداد: text_<key>_<lang>)
"""
from __future__ import annotations

from locales import ar, en

_LOCALES = {"ar": ar.TEXTS, "en": en.TEXTS}

SUPPORTED_LANGUAGES = list(_LOCALES.keys())


def get_text(lang: str, key: str, **kwargs) -> str:
    texts = _LOCALES.get(lang, _LOCALES["ar"])
    template = texts.get(key) or _LOCALES["ar"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


async def get_text_db(session, lang: str, key: str, **kwargs) -> str:
    """نسخة تدعم التخصيص من قاعدة البيانات (جدول settings) إن وُجد override."""
    from database.repository import SettingsRepository

    settings_repo = SettingsRepository(session)
    override = await settings_repo.get(f"text_{key}_{lang}", "")
    template = override or _LOCALES.get(lang, _LOCALES["ar"]).get(key) or _LOCALES["ar"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
