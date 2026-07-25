"""
خدمة عضوية VIP - التفعيل، التجديد، الترقية، الانتهاء التلقائي، التذكيرات
"""
from __future__ import annotations

from datetime import datetime, timedelta

from database.models import DURATION_DAYS, VipPlan, VipSubscription
from database.repository import VipSubscriptionRepository


def calculate_expiry(plan: VipPlan, from_date: datetime | None = None) -> datetime | None:
    days = DURATION_DAYS.get(plan.duration, 30)
    if days == 0:
        return None  # Lifetime
    base = from_date or datetime.utcnow()
    return base + timedelta(days=days)


async def activate_subscription(session, user_id: int, plan: VipPlan) -> VipSubscription:
    """تفعيل اشتراك جديد. إذا كان لدى المستخدم اشتراك فعّال يتم تمديد الفترة الحالية (ترقية/تجديد)."""
    sub_repo = VipSubscriptionRepository(session)
    current = await sub_repo.get_active_for_user(user_id)

    base_date = datetime.utcnow()
    if current and current.expires_at and current.expires_at > base_date:
        base_date = current.expires_at
        await sub_repo.cancel(current)  # نغلق الاشتراك القديم ونبدأ سجلًا جديدًا بتاريخ ممتد

    expires_at = calculate_expiry(plan, base_date)
    return await sub_repo.create(user_id, plan.id, expires_at)


async def get_vip_status(session, user_id: int) -> tuple[bool, VipSubscription | None]:
    sub_repo = VipSubscriptionRepository(session)
    sub = await sub_repo.get_active_for_user(user_id)
    if not sub:
        return False, None
    if sub.expires_at and sub.expires_at <= datetime.utcnow():
        await sub_repo.mark_expired(sub)
        return False, None
    return True, sub


async def run_expiration_sweep(session) -> list[VipSubscription]:
    """يُستدعى دوريًا لإغلاق الاشتراكات المنتهية."""
    sub_repo = VipSubscriptionRepository(session)
    expired = await sub_repo.list_expired(datetime.utcnow())
    for sub in expired:
        await sub_repo.mark_expired(sub)
    return expired


async def run_reminder_sweep(session, days_before: int = 3) -> list[VipSubscription]:
    """يُستدعى دوريًا لتحديد الاشتراكات التي توشك على الانتهاء."""
    sub_repo = VipSubscriptionRepository(session)
    threshold = datetime.utcnow() + timedelta(days=days_before)
    due = await sub_repo.list_expiring_soon(threshold)
    return due
