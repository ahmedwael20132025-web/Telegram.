"""
إعدادات المشروع - يتم تحميلها من متغيرات البيئة (.env)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_int_list(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


@dataclass(frozen=True)
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    super_admins: list[int] = field(
        default_factory=lambda: _get_int_list(os.getenv("SUPER_ADMINS", ""))
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'bot.db'}"
        )
    )
    claude_api_key: str = field(default_factory=lambda: os.getenv("CLAUDE_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    default_ai_provider: str = field(
        default_factory=lambda: os.getenv("DEFAULT_AI_PROVIDER", "google")
    )
    # يمكن ضبط DATA_DIR على مسار Volume دائم عند النشر على Railway أو أي استضافة
    # بنظام ملفات مؤقت (ephemeral)، لضمان بقاء قاعدة البيانات والنسخ الاحتياطية بعد كل نشر.
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR))))
    backups_dir: Path = field(init=False)
    generated_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN غير موجود في ملف .env")
        object.__setattr__(self, "backups_dir", self.data_dir / "backups")
        object.__setattr__(self, "generated_dir", self.data_dir / "generated")
        object.__setattr__(self, "logs_dir", self.data_dir / "logs")
        for path in (self.backups_dir, self.generated_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


config = Config()
