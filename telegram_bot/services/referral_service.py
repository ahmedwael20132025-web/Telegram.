"""
خدمة نظام الإحالة - منح المكافآت عند تحقق الشروط
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, WalletOpType
from database.repository import (
    ReferralRepository,
    SettingsRepository,
    UserRepository,
)


async def process_referral_reward(session: AsyncSession, referred_user_id: int) -> None:
    """يُستدعى بعد أول استخدام ناجح للمستخدم المُحال، لمنح المكافأة لصاحب الدعوة."""
    settings_repo = SettingsRepository(session)
    referral_repo = ReferralRepository(session)
    user_repo = UserRepository(session)

    if not await settings_repo.get_bool("referral_enabled", True):
        return

    referral = await referral_repo.get_for_referred(referred_user_id)
    if not referral or referral.reward_granted:
        return

    min_invites = await settings_repo.get_int("referral_min_invites", 1)
    invites_count = await user_repo.count_referrals(referral.referrer_id)
    if invites_count < min_invites:
        return

    reward_type = await settings_repo.get("referral_reward_type", "wallet")
    reward_value = await settings_repo.get_float("referral_reward_value", 5)

    result = await session.execute(select(User).where(User.id == referral.referrer_id))
    referrer = result.scalar_one_or_none()
    if not referrer:
        return

    if reward_type == "free_credit":
        referrer.free_credits += int(reward_value)
        await session.commit()
    else:
        await user_repo.adjust_wallet(
            referrer, reward_value, WalletOpType.referral_bonus, note="مكافأة إحالة"
        )

    await referral_repo.mark_rewarded(referral)
