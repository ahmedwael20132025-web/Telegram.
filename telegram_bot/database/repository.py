"""
طبقة الوصول لقاعدة البيانات (Repository Pattern)
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Admin,
    AIRequest,
    BroadcastLog,
    ButtonConfig,
    Channel,
    CodeFile,
    Coupon,
    CouponUsage,
    Log,
    Page,
    PageTranslation,
    Payment,
    PaymentMethod,
    PaymentStatus,
    ProjectTemplate,
    GeneratedProject,
    GeneratedProjectStatus,
    Purchase,
    Referral,
    Setting,
    Statistic,
    User,
    VipPlan,
    VipSubscription,
    VipSubscriptionStatus,
    WalletTransaction,
    WithdrawRequest,
)


def _gen_ref_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------- Users ----
class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ref_code(self, code: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str,
        default_free_credits: int,
        referrer_code: str | None = None,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False

        referrer = None
        if referrer_code:
            referrer = await self.get_by_ref_code(referrer_code)

        code = _gen_ref_code()
        while await self.get_by_ref_code(code):
            code = _gen_ref_code()

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            free_credits=default_free_credits,
            referral_code=code,
            referrer_id=referrer.id if referrer else None,
        )
        self.session.add(user)
        await self.session.flush()

        if referrer:
            self.session.add(Referral(referrer_id=referrer.id, referred_id=user.id))

        await self.session.commit()
        return user, True

    async def set_banned(self, telegram_id: int, banned: bool) -> None:
        await self.session.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_banned=banned)
        )
        await self.session.commit()

    async def decrement_free_credit(self, user: User) -> None:
        user.free_credits = max(0, user.free_credits - 1)
        await self.session.commit()

    async def adjust_wallet(
        self, user: User, amount: float, op_type: str, note: str = ""
    ) -> float:
        user.wallet_balance = round(user.wallet_balance + amount, 2)
        self.session.add(
            WalletTransaction(
                user_id=user.id,
                op_type=op_type,
                amount=amount,
                balance_after=user.wallet_balance,
                note=note,
            )
        )
        await self.session.commit()
        return user.wallet_balance

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def count_referrals(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
        )
        return result.scalar_one()

    async def search(self, telegram_id: int) -> User | None:
        return await self.get_by_telegram_id(telegram_id)

    async def list_all_active(self) -> list[User]:
        result = await self.session.execute(select(User).where(User.is_banned.is_(False)))
        return list(result.scalars().all())


# --------------------------------------------------------------- Admins ----
class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_admin(self, telegram_id: int, super_admins: list[int]) -> bool:
        if telegram_id in super_admins:
            return True
        result = await self.session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none() is not None

    async def add(self, telegram_id: int, added_by: int) -> None:
        exists = await self.session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )
        if exists.scalar_one_or_none():
            return
        self.session.add(Admin(telegram_id=telegram_id, added_by=added_by))
        await self.session.commit()

    async def remove(self, telegram_id: int) -> None:
        await self.session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )
        result = await self.session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )
        admin = result.scalar_one_or_none()
        if admin:
            await self.session.delete(admin)
            await self.session.commit()

    async def list_all(self) -> list[Admin]:
        result = await self.session.execute(select(Admin))
        return list(result.scalars().all())


# ------------------------------------------------------------- Settings ----
class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str = "") -> str:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def set(self, key: str, value: str) -> None:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            self.session.add(Setting(key=key, value=value))
        await self.session.commit()

    async def get_int(self, key: str, default: int = 0) -> int:
        val = await self.get(key, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        val = await self.get(key, str(default))
        try:
            return float(val)
        except ValueError:
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        val = await self.get(key, str(default))
        return val.lower() in ("1", "true", "yes")


# --------------------------------------------------------- PaymentMethod ---
class PaymentMethodRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod).order_by(PaymentMethod.sort_order)
        )
        return list(result.scalars().all())

    async def get(self, method_id: int) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(PaymentMethod.id == method_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(PaymentMethod.code == code)
        )
        return result.scalar_one_or_none()

    async def create(
        self, code: str, name: str, price: float, currency: str, instructions: str
    ) -> PaymentMethod:
        method = PaymentMethod(
            code=code, name=name, price=price, currency=currency, instructions=instructions
        )
        self.session.add(method)
        await self.session.commit()
        return method

    async def toggle(self, method_id: int) -> None:
        method = await self.get(method_id)
        if method:
            method.is_active = not method.is_active
            await self.session.commit()

    async def update_fields(self, method_id: int, **fields) -> None:
        method = await self.get(method_id)
        if not method:
            return
        for key, value in fields.items():
            setattr(method, key, value)
        await self.session.commit()


# --------------------------------------------------------------- Payment ---
class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        method_id: int,
        amount: float,
        purpose: str,
        reference: str | None = None,
        proof_file_id: str | None = None,
        status: str = PaymentStatus.pending,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            method_id=method_id,
            amount=amount,
            purpose=purpose,
            reference=reference,
            proof_file_id=proof_file_id,
            status=status,
        )
        self.session.add(payment)
        await self.session.commit()
        return payment

    async def get(self, payment_id: int) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def set_status(self, payment_id: int, status: str, decided_by: int) -> Payment | None:
        payment = await self.get(payment_id)
        if not payment:
            return None
        payment.status = status
        payment.decided_by = decided_by
        payment.decided_at = datetime.utcnow()
        await self.session.commit()
        return payment

    async def list_pending(self) -> list[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.status == PaymentStatus.pending)
        )
        return list(result.scalars().all())

    async def sum_approved(self) -> float:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
                Payment.status == PaymentStatus.approved
            )
        )
        return float(result.scalar_one())


# ------------------------------------------------------------- CodeFile ----
class CodeFileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self, category: str | None = None) -> list[CodeFile]:
        stmt = select(CodeFile).where(CodeFile.is_active.is_(True))
        if category:
            stmt = stmt.where(CodeFile.category == category)
        result = await self.session.execute(stmt.order_by(CodeFile.id.desc()))
        return list(result.scalars().all())

    async def list_all(self) -> list[CodeFile]:
        result = await self.session.execute(select(CodeFile).order_by(CodeFile.id.desc()))
        return list(result.scalars().all())

    async def get(self, file_id: int) -> CodeFile | None:
        result = await self.session.execute(select(CodeFile).where(CodeFile.id == file_id))
        return result.scalar_one_or_none()

    async def create(self, **fields) -> CodeFile:
        item = CodeFile(**fields)
        self.session.add(item)
        await self.session.commit()
        return item

    async def update_fields(self, file_id: int, **fields) -> None:
        item = await self.get(file_id)
        if not item:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        await self.session.commit()

    async def toggle(self, file_id: int) -> None:
        item = await self.get(file_id)
        if item:
            item.is_active = not item.is_active
            await self.session.commit()

    async def increment_downloads(self, file_id: int) -> None:
        item = await self.get(file_id)
        if item:
            item.downloads += 1
            await self.session.commit()

    async def categories(self) -> list[str]:
        result = await self.session.execute(
            select(CodeFile.category).where(CodeFile.is_active.is_(True)).distinct()
        )
        return [row[0] for row in result.all()]


# ------------------------------------------------------------- Purchase ----
class PurchaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, item_type: str, item_id: int | None, amount: float) -> Purchase:
        purchase = Purchase(user_id=user_id, item_type=item_type, item_id=item_id, amount=amount)
        self.session.add(purchase)
        await self.session.commit()
        return purchase

    async def list_for_user(self, user_id: int) -> list[Purchase]:
        result = await self.session.execute(
            select(Purchase).where(Purchase.user_id == user_id).order_by(Purchase.id.desc())
        )
        return list(result.scalars().all())

    async def has_purchased_file(self, user_id: int, file_id: int) -> bool:
        result = await self.session.execute(
            select(Purchase).where(
                Purchase.user_id == user_id,
                Purchase.item_type == "file",
                Purchase.item_id == file_id,
            )
        )
        return result.scalar_one_or_none() is not None


# --------------------------------------------------------------- Button ----
class ButtonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_visible(self, menu: str = "main") -> list[ButtonConfig]:
        result = await self.session.execute(
            select(ButtonConfig)
            .where(
                ButtonConfig.menu == menu,
                ButtonConfig.is_visible.is_(True),
                ButtonConfig.is_enabled.is_(True),
            )
            .order_by(ButtonConfig.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self, menu: str = "main") -> list[ButtonConfig]:
        result = await self.session.execute(
            select(ButtonConfig).where(ButtonConfig.menu == menu).order_by(ButtonConfig.sort_order)
        )
        return list(result.scalars().all())

    async def get(self, button_id: int) -> ButtonConfig | None:
        result = await self.session.execute(
            select(ButtonConfig).where(ButtonConfig.id == button_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> ButtonConfig | None:
        result = await self.session.execute(
            select(ButtonConfig).where(ButtonConfig.code == code)
        )
        return result.scalar_one_or_none()

    async def list_visible_children(self, parent_code: str) -> list[ButtonConfig]:
        result = await self.session.execute(
            select(ButtonConfig)
            .where(
                ButtonConfig.parent_code == parent_code,
                ButtonConfig.is_visible.is_(True),
                ButtonConfig.is_enabled.is_(True),
            )
            .order_by(ButtonConfig.sort_order)
        )
        return list(result.scalars().all())

    async def reorder(self, ordered_ids: list[int]) -> None:
        for index, button_id in enumerate(ordered_ids):
            await self.session.execute(
                update(ButtonConfig).where(ButtonConfig.id == button_id).values(sort_order=index)
            )
        await self.session.commit()

    async def create(self, **fields) -> ButtonConfig:
        btn = ButtonConfig(**fields)
        self.session.add(btn)
        await self.session.commit()
        return btn

    async def update_fields(self, button_id: int, **fields) -> None:
        btn = await self.get(button_id)
        if not btn:
            return
        for key, value in fields.items():
            setattr(btn, key, value)
        await self.session.commit()

    async def delete(self, button_id: int) -> None:
        btn = await self.get(button_id)
        if btn:
            await self.session.delete(btn)
            await self.session.commit()


# -------------------------------------------------------------- Channel ----
class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[Channel]:
        result = await self.session.execute(
            select(Channel).where(Channel.is_active.is_(True)).order_by(Channel.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Channel]:
        result = await self.session.execute(select(Channel).order_by(Channel.sort_order))
        return list(result.scalars().all())

    async def get(self, channel_id: int) -> Channel | None:
        result = await self.session.execute(select(Channel).where(Channel.id == channel_id))
        return result.scalar_one_or_none()

    async def create(self, chat_id: str, title: str, invite_link: str) -> Channel:
        channel = Channel(chat_id=chat_id, title=title, invite_link=invite_link)
        self.session.add(channel)
        await self.session.commit()
        return channel

    async def update_fields(self, channel_id: int, **fields) -> None:
        channel = await self.get(channel_id)
        if not channel:
            return
        for key, value in fields.items():
            setattr(channel, key, value)
        await self.session.commit()

    async def delete(self, channel_id: int) -> None:
        channel = await self.get(channel_id)
        if channel:
            await self.session.delete(channel)
            await self.session.commit()


# ------------------------------------------------------------- Referral ----
class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_referred(self, referred_id: int) -> Referral | None:
        result = await self.session.execute(
            select(Referral).where(Referral.referred_id == referred_id)
        )
        return result.scalar_one_or_none()

    async def mark_rewarded(self, referral: Referral) -> None:
        referral.reward_granted = True
        await self.session.commit()


# ------------------------------------------------------------ Withdrawal ---
class WithdrawRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, amount: float, details: str) -> WithdrawRequest:
        req = WithdrawRequest(user_id=user_id, amount=amount, details=details)
        self.session.add(req)
        await self.session.commit()
        return req

    async def get(self, request_id: int) -> WithdrawRequest | None:
        result = await self.session.execute(
            select(WithdrawRequest).where(WithdrawRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(self) -> list[WithdrawRequest]:
        result = await self.session.execute(
            select(WithdrawRequest).where(WithdrawRequest.status == PaymentStatus.pending)
        )
        return list(result.scalars().all())

    async def set_status(self, request_id: int, status: str) -> WithdrawRequest | None:
        req = await self.get(request_id)
        if not req:
            return None
        req.status = status
        req.decided_at = datetime.utcnow()
        await self.session.commit()
        return req


# --------------------------------------------------------------- Coupon ----
class CouponRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Coupon | None:
        result = await self.session.execute(select(Coupon).where(Coupon.code == code))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Coupon]:
        result = await self.session.execute(select(Coupon).order_by(Coupon.id.desc()))
        return list(result.scalars().all())

    async def create(self, **fields) -> Coupon:
        coupon = Coupon(**fields)
        self.session.add(coupon)
        await self.session.commit()
        return coupon

    async def delete(self, coupon_id: int) -> None:
        result = await self.session.execute(select(Coupon).where(Coupon.id == coupon_id))
        coupon = result.scalar_one_or_none()
        if coupon:
            await self.session.delete(coupon)
            await self.session.commit()

    async def toggle(self, coupon_id: int) -> None:
        result = await self.session.execute(select(Coupon).where(Coupon.id == coupon_id))
        coupon = result.scalar_one_or_none()
        if coupon:
            coupon.is_active = not coupon.is_active
            await self.session.commit()

    async def has_used(self, coupon_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(CouponUsage).where(
                CouponUsage.coupon_id == coupon_id, CouponUsage.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def register_usage(self, coupon: Coupon, user_id: int) -> None:
        self.session.add(CouponUsage(coupon_id=coupon.id, user_id=user_id))
        coupon.used_count += 1
        await self.session.commit()


# ------------------------------------------------------------------ Logs ---
class LogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, message: str, level: str = "info", source: str = "") -> None:
        self.session.add(Log(message=message, level=level, source=source))
        await self.session.commit()

    async def recent(self, limit: int = 20) -> list[Log]:
        result = await self.session.execute(
            select(Log).order_by(Log.id.desc()).limit(limit)
        )
        return list(result.scalars().all())


# ------------------------------------------------------------ AI Request ---
class AIRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, provider: str, prompt: str, response_summary: str, success: bool
    ) -> AIRequest:
        req = AIRequest(
            user_id=user_id,
            provider=provider,
            prompt=prompt,
            response_summary=response_summary,
            success=success,
        )
        self.session.add(req)
        await self.session.commit()
        return req

    async def count_for_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(AIRequest.id)).where(AIRequest.user_id == user_id)
        )
        return result.scalar_one()

    async def count_total(self) -> int:
        result = await self.session.execute(select(func.count(AIRequest.id)))
        return result.scalar_one()


# ------------------------------------------------------------- Statistic ---
class StatisticRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_or_create_today(self) -> Statistic:
        today = date.today().isoformat()
        result = await self.session.execute(
            select(Statistic).where(Statistic.date == today)
        )
        row = result.scalar_one_or_none()
        if not row:
            row = Statistic(date=today)
            self.session.add(row)
            await self.session.flush()
        return row

    async def bump_new_user(self) -> None:
        row = await self._get_or_create_today()
        row.new_users += 1
        await self.session.commit()

    async def bump_code_generation(self) -> None:
        row = await self._get_or_create_today()
        row.code_generations += 1
        await self.session.commit()

    async def bump_file_sale(self, revenue: float) -> None:
        row = await self._get_or_create_today()
        row.files_sold += 1
        row.revenue = round(row.revenue + revenue, 2)
        await self.session.commit()

    async def add_revenue(self, amount: float) -> None:
        row = await self._get_or_create_today()
        row.revenue = round(row.revenue + amount, 2)
        await self.session.commit()

    async def totals(self, days: int) -> dict:
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(Statistic.new_users), 0),
                func.coalesce(func.sum(Statistic.code_generations), 0),
                func.coalesce(func.sum(Statistic.files_sold), 0),
                func.coalesce(func.sum(Statistic.revenue), 0.0),
            ).order_by(Statistic.date.desc()).limit(days)
        )
        row = result.first()
        return {
            "new_users": row[0] if row else 0,
            "code_generations": row[1] if row else 0,
            "files_sold": row[2] if row else 0,
            "revenue": row[3] if row else 0.0,
        }


# ----------------------------------------------------------------- Pages ---
class PageRepository:
    """إدارة الصفحات الديناميكية وترجماتها (Dynamic Pages & Navigation Builder)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[Page]:
        result = await self.session.execute(select(Page).order_by(Page.sort_order))
        return list(result.scalars().all())

    async def list_visible(self) -> list[Page]:
        result = await self.session.execute(
            select(Page).where(Page.is_visible.is_(True)).order_by(Page.sort_order)
        )
        return list(result.scalars().all())

    async def get(self, page_id: int) -> Page | None:
        result = await self.session.execute(select(Page).where(Page.id == page_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Page | None:
        result = await self.session.execute(select(Page).where(Page.code == code))
        return result.scalar_one_or_none()

    async def create(
        self, code: str, sort_order: int = 0, access_level: str = "all"
    ) -> Page:
        page = Page(code=code, sort_order=sort_order, access_level=access_level)
        self.session.add(page)
        await self.session.commit()
        return page

    async def update_fields(self, page_id: int, **fields) -> None:
        page = await self.get(page_id)
        if not page:
            return
        for key, value in fields.items():
            setattr(page, key, value)
        await self.session.commit()

    async def toggle_visibility(self, page_id: int) -> None:
        page = await self.get(page_id)
        if page:
            page.is_visible = not page.is_visible
            await self.session.commit()

    async def delete(self, page_id: int) -> None:
        page = await self.get(page_id)
        if page:
            await self.session.delete(page)
            await self.session.commit()

    async def reorder(self, ordered_ids: list[int]) -> None:
        for index, page_id in enumerate(ordered_ids):
            await self.session.execute(
                update(Page).where(Page.id == page_id).values(sort_order=index)
            )
        await self.session.commit()

    # ---- الترجمات ----
    async def get_translation(self, page_id: int, language: str) -> PageTranslation | None:
        result = await self.session.execute(
            select(PageTranslation).where(
                PageTranslation.page_id == page_id, PageTranslation.language == language
            )
        )
        return result.scalar_one_or_none()

    async def list_translations(self, page_id: int) -> list[PageTranslation]:
        result = await self.session.execute(
            select(PageTranslation).where(PageTranslation.page_id == page_id)
        )
        return list(result.scalars().all())

    async def upsert_translation(self, page_id: int, language: str, **fields) -> PageTranslation:
        translation = await self.get_translation(page_id, language)
        if translation:
            for key, value in fields.items():
                setattr(translation, key, value)
        else:
            translation = PageTranslation(page_id=page_id, language=language, **fields)
            self.session.add(translation)
        await self.session.commit()
        return translation

    async def get_content(self, code: str, language: str) -> tuple[Page, PageTranslation] | None:
        """يجلب الصفحة ومحتواها بلغة معينة، مع رجوع تلقائي للعربية إذا لم تتوفر الترجمة."""
        page = await self.get_by_code(code)
        if not page:
            return None
        translation = await self.get_translation(page.id, language)
        if not translation:
            translation = await self.get_translation(page.id, "ar")
        if not translation:
            translations = await self.list_translations(page.id)
            translation = translations[0] if translations else None
        if not translation:
            return None
        return page, translation


# ------------------------------------------------------ Project Generator --
class ProjectTemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[ProjectTemplate]:
        result = await self.session.execute(
            select(ProjectTemplate)
            .where(ProjectTemplate.is_active.is_(True))
            .order_by(ProjectTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[ProjectTemplate]:
        result = await self.session.execute(
            select(ProjectTemplate).order_by(ProjectTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def get(self, template_id: int) -> ProjectTemplate | None:
        result = await self.session.execute(
            select(ProjectTemplate).where(ProjectTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> ProjectTemplate:
        template = ProjectTemplate(**fields)
        self.session.add(template)
        await self.session.commit()
        return template

    async def toggle(self, template_id: int) -> None:
        template = await self.get(template_id)
        if template:
            template.is_active = not template.is_active
            await self.session.commit()

    async def delete(self, template_id: int) -> None:
        template = await self.get(template_id)
        if template:
            await self.session.delete(template)
            await self.session.commit()


class GeneratedProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, description: str, template_id: int | None = None) -> GeneratedProject:
        project = GeneratedProject(user_id=user_id, description=description, template_id=template_id)
        self.session.add(project)
        await self.session.commit()
        return project

    async def set_status(self, project_id: int, status: str, **fields) -> None:
        result = await self.session.execute(
            select(GeneratedProject).where(GeneratedProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return
        project.status = status
        for key, value in fields.items():
            setattr(project, key, value)
        await self.session.commit()

    async def list_recent(self, limit: int = 20) -> list[GeneratedProject]:
        result = await self.session.execute(
            select(GeneratedProject).order_by(GeneratedProject.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: str) -> int:
        result = await self.session.execute(
            select(func.count(GeneratedProject.id)).where(GeneratedProject.status == status)
        )
        return result.scalar_one()


# ------------------------------------------------------------------ VIP ----
class VipPlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[VipPlan]:
        result = await self.session.execute(
            select(VipPlan).where(VipPlan.is_active.is_(True)).order_by(VipPlan.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[VipPlan]:
        result = await self.session.execute(select(VipPlan).order_by(VipPlan.sort_order))
        return list(result.scalars().all())

    async def get(self, plan_id: int) -> VipPlan | None:
        result = await self.session.execute(select(VipPlan).where(VipPlan.id == plan_id))
        return result.scalar_one_or_none()

    async def create(self, **fields) -> VipPlan:
        plan = VipPlan(**fields)
        self.session.add(plan)
        await self.session.commit()
        return plan

    async def update_fields(self, plan_id: int, **fields) -> None:
        plan = await self.get(plan_id)
        if not plan:
            return
        for key, value in fields.items():
            setattr(plan, key, value)
        await self.session.commit()

    async def toggle(self, plan_id: int) -> None:
        plan = await self.get(plan_id)
        if plan:
            plan.is_active = not plan.is_active
            await self.session.commit()

    async def delete(self, plan_id: int) -> None:
        plan = await self.get(plan_id)
        if plan:
            await self.session.delete(plan)
            await self.session.commit()


class VipSubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_for_user(self, user_id: int) -> VipSubscription | None:
        result = await self.session.execute(
            select(VipSubscription)
            .where(
                VipSubscription.user_id == user_id,
                VipSubscription.status == VipSubscriptionStatus.active,
            )
            .order_by(VipSubscription.id.desc())
        )
        return result.scalars().first()

    async def create(
        self, user_id: int, plan_id: int, expires_at: datetime | None
    ) -> VipSubscription:
        sub = VipSubscription(user_id=user_id, plan_id=plan_id, expires_at=expires_at)
        self.session.add(sub)
        await self.session.commit()
        return sub

    async def history_for_user(self, user_id: int) -> list[VipSubscription]:
        result = await self.session.execute(
            select(VipSubscription)
            .where(VipSubscription.user_id == user_id)
            .order_by(VipSubscription.id.desc())
        )
        return list(result.scalars().all())

    async def list_expiring_soon(self, before: datetime) -> list[VipSubscription]:
        result = await self.session.execute(
            select(VipSubscription).where(
                VipSubscription.status == VipSubscriptionStatus.active,
                VipSubscription.expires_at.is_not(None),
                VipSubscription.expires_at <= before,
                VipSubscription.reminder_sent.is_(False),
            )
        )
        return list(result.scalars().all())

    async def list_expired(self, now: datetime) -> list[VipSubscription]:
        result = await self.session.execute(
            select(VipSubscription).where(
                VipSubscription.status == VipSubscriptionStatus.active,
                VipSubscription.expires_at.is_not(None),
                VipSubscription.expires_at <= now,
            )
        )
        return list(result.scalars().all())

    async def mark_reminder_sent(self, sub: VipSubscription) -> None:
        sub.reminder_sent = True
        await self.session.commit()

    async def mark_expired(self, sub: VipSubscription) -> None:
        sub.status = VipSubscriptionStatus.expired
        await self.session.commit()

    async def cancel(self, sub: VipSubscription) -> None:
        sub.status = VipSubscriptionStatus.cancelled
        await self.session.commit()

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count(VipSubscription.id)).where(
                VipSubscription.status == VipSubscriptionStatus.active
            )
        )
        return result.scalar_one()


# --------------------------------------------------------------- Broadcast -
class BroadcastLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, sent: int, failed: int) -> BroadcastLog:
        log = BroadcastLog(sent_count=sent, failed_count=failed)
        self.session.add(log)
        await self.session.commit()
        return log
