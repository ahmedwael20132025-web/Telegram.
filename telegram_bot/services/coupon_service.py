"""
خدمة التحقق من الكوبونات وتطبيق الخصم
"""
from __future__ import annotations

from datetime import datetime

from database.models import Coupon, CouponType
from database.repository import CouponRepository


class CouponError(Exception):
    pass


async def validate_and_apply(
    session, code: str, user_id: int, original_price: float
) -> tuple[Coupon, float]:
    repo = CouponRepository(session)
    coupon = await repo.get_by_code(code.strip())

    if not coupon or not coupon.is_active:
        raise CouponError("الكوبون غير صالح.")

    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        raise CouponError("انتهت صلاحية الكوبون.")

    if coupon.used_count >= coupon.max_uses:
        raise CouponError("تم استنفاد عدد مرات استخدام هذا الكوبون.")

    if not coupon.is_public and coupon.assigned_user_id != user_id:
        raise CouponError("هذا الكوبون غير مخصص لك.")

    if await repo.has_used(coupon.id, user_id):
        raise CouponError("لقد استخدمت هذا الكوبون من قبل.")

    if coupon.coupon_type == CouponType.percent:
        discount = original_price * (coupon.value / 100)
    else:
        discount = coupon.value

    final_price = max(0.0, round(original_price - discount, 2))
    return coupon, final_price
