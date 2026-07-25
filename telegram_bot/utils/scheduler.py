"""
مهام مجدولة: نسخ احتياطي تلقائي يومي
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from database.engine import async_session_maker
from database.repository import SettingsRepository
from services.backup_service import create_backup
from utils.logger import logger


async def _seconds_until_hour(target_hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def vip_maintenance_loop() -> None:
    """يعمل كل ساعة: يغلق الاشتراكات المنتهية ويرسل تذكيرات قبل الانتهاء."""
    from services.vip_service import run_expiration_sweep, run_reminder_sweep
    from database.repository import VipPlanRepository, VipSubscriptionRepository
    from sqlalchemy import select
    from database.models import User

    while True:
        async with async_session_maker() as session:
            try:
                await run_expiration_sweep(session)
                due = await run_reminder_sweep(session, days_before=3)
                sub_repo = VipSubscriptionRepository(session)
                plan_repo = VipPlanRepository(session)

                for sub in due:
                    result = await session.execute(select(User).where(User.id == sub.user_id))
                    user = result.scalar_one_or_none()
                    plan = await plan_repo.get(sub.plan_id)
                    if user and plan:
                        try:
                            from bot import bot_instance  # يُحقن لاحقًا عند التشغيل الفعلي

                            await bot_instance.send_message(
                                user.telegram_id,
                                f"⏰ تذكير: اشتراكك في {plan.badge} {plan.name} سينتهي قريبًا. جدّده الآن لتجنب انقطاع الخدمة.",
                            )
                        except Exception:
                            pass
                    await sub_repo.mark_reminder_sent(sub)
            except Exception as exc:  # noqa: BLE001
                logger.error("خطأ في مهمة صيانة VIP: %s", exc)

        await asyncio.sleep(3600)


async def auto_backup_loop() -> None:
    while True:
        async with async_session_maker() as session:
            settings_repo = SettingsRepository(session)
            enabled = await settings_repo.get_bool("auto_backup_enabled", True)
            target_hour = await settings_repo.get_int("auto_backup_hour", 3)

        if enabled:
            wait_seconds = await _seconds_until_hour(target_hour)
            await asyncio.sleep(wait_seconds)
            try:
                path = create_backup()
                if path:
                    logger.info("تم إنشاء نسخة احتياطية تلقائية: %s", path.name)
            except Exception as exc:  # noqa: BLE001
                logger.error("فشل النسخ الاحتياطي التلقائي: %s", exc)
        else:
            await asyncio.sleep(3600)
