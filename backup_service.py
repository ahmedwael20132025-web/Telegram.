"""
خدمة النسخ الاحتياطي لقاعدة البيانات (SQLite)
يعمل تلقائيًا فقط عند استخدام SQLite. مع PostgreSQL يُنصح باستخدام pg_dump خارجيًا.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config import config

DB_FILE_PREFIX = "sqlite+aiosqlite:///"


def _sqlite_path() -> Path | None:
    if not config.database_url.startswith(DB_FILE_PREFIX):
        return None
    return Path(config.database_url.removeprefix(DB_FILE_PREFIX))


def create_backup() -> Path | None:
    """ينشئ نسخة احتياطية ويحذف الأقدم إذا تجاوز العدد المسموح."""
    db_path = _sqlite_path()
    if not db_path or not db_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config.backups_dir / f"backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)

    _cleanup_old_backups()
    return backup_path


def _cleanup_old_backups(keep: int = 10) -> None:
    backups = sorted(
        config.backups_dir.glob("backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for old_backup in backups[keep:]:
        old_backup.unlink(missing_ok=True)


def list_backups() -> list[Path]:
    return sorted(
        config.backups_dir.glob("backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )


def restore_backup(backup_path: Path) -> bool:
    db_path = _sqlite_path()
    if not db_path or not backup_path.exists():
        return False
    shutil.copy2(backup_path, db_path)
    return True
