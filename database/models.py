"""
نماذج قاعدة البيانات (SQLAlchemy 2.0 async ORM)
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.engine import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CouponType(str, enum.Enum):
    percent = "percent"
    fixed = "fixed"


class WalletOpType(str, enum.Enum):
    referral_bonus = "referral_bonus"
    refund = "refund"
    admin_gift = "admin_gift"
    purchase = "purchase"
    withdraw = "withdraw"
    admin_deduct = "admin_deduct"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(8), default="ar")

    free_credits: Mapped[int] = mapped_column(Integer, default=0)
    wallet_balance: Mapped[float] = mapped_column(Float, default=0.0)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    referrer: Mapped["User"] = relationship(remote_side=[id])


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_super: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    instructions: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(16), default="EGP")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    method_id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"))
    amount: Mapped[float] = mapped_column(Float)
    purpose: Mapped[str] = mapped_column(String(64))  # code_generation / file / topup
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        String(16), default=PaymentStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    user: Mapped["User"] = relationship()
    method: Mapped["PaymentMethod"] = relationship()


class CodeFile(Base):
    __tablename__ = "code_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="عام")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    file_id: Mapped[str] = mapped_column(String(256))
    photo_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_type: Mapped[str] = mapped_column(String(32))  # file / code_generation
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class ButtonActionType(str, enum.Enum):
    feature = "feature"      # ميزة مدمجة بالكود (wallet, referral, ...)
    page = "page"            # صفحة ديناميكية منشأة من لوحة الأدمن
    url = "url"              # رابط خارجي
    channel = "channel"      # قناة تيليجرام
    custom = "custom"        # إجراء مخصص يحدده الأدمن (callback نصي حر)


class ButtonConfig(Base):
    __tablename__ = "buttons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    text: Mapped[str] = mapped_column(String(128))
    emoji: Mapped[str] = mapped_column(String(16), default="")
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    feature: Mapped[str] = mapped_column(String(64), default="")  # للتوافق القديم

    # نظام التنقل الديناميكي (Dynamic Navigation Builder)
    action_type: Mapped[str] = mapped_column(String(16), default=ButtonActionType.feature)
    target: Mapped[str] = mapped_column(String(255), default="")  # page code / url / channel chat_id / feature name / custom action id
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # لبناء قوائم فرعية (زر داخل صفحة)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    menu: Mapped[str] = mapped_column(String(16), default="main")  # main / admin / page

    # صلاحيات الوصول: all / subscribers_only / admins_only
    access_level: Mapped[str] = mapped_column(String(24), default="all")


class Page(Base):
    """صفحة ديناميكية بالكامل من لوحة الأدمن، بدون الحاجة لتعديل الكود."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    # صلاحيات الوصول: all / subscribers_only / admins_only
    access_level: Mapped[str] = mapped_column(String(24), default="all")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    translations: Mapped[list["PageTranslation"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class PageTranslation(Base):
    """محتوى الصفحة بلغة معينة (عنوان، وصف، نص، وسائط)."""

    __tablename__ = "page_translations"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"))
    language: Mapped[str] = mapped_column(String(8))

    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(String(512), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")  # نص منسق (Markdown/HTML)

    image_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    video_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    document_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    page: Mapped["Page"] = relationship(back_populates="translations")

    __table_args__ = (UniqueConstraint("page_id", "language"),)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[str] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    reward_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    op_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float)  # موجب = إضافة، سالب = خصم
    balance_after: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    details: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[PaymentStatus] = mapped_column(
        String(16), default=PaymentStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship()


class VipDuration(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"
    lifetime = "lifetime"


DURATION_DAYS = {
    VipDuration.monthly: 30,
    VipDuration.quarterly: 90,
    VipDuration.yearly: 365,
    VipDuration.lifetime: 0,
}


class VipPlan(Base):
    __tablename__ = "vip_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    badge: Mapped[str] = mapped_column(String(32), default="⭐")
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[str] = mapped_column(Text, default="")  # سطر لكل ميزة
    price: Mapped[float] = mapped_column(Float)
    duration: Mapped[str] = mapped_column(String(16), default=VipDuration.monthly)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VipSubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class VipSubscription(Base):
    __tablename__ = "vip_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("vip_plans.id"))
    status: Mapped[str] = mapped_column(String(16), default=VipSubscriptionStatus.active)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()
    plan: Mapped["VipPlan"] = relationship()


class ProjectTemplate(Base):
    """قالب جاهز يُستخدم كنقطة انطلاق لمولّد المشاريع بالذكاء الاصطناعي."""

    __tablename__ = "project_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    prompt_prefix: Mapped[str] = mapped_column(Text, default="")  # يُضاف قبل وصف المستخدم عند التوليد
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class GeneratedProjectStatus(str, enum.Enum):
    queued = "queued"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class GeneratedProject(Base):
    """سجل مشاريع مولّد الذكاء الاصطناعي (يخدم شاشات الإدارة: المشاريع المولدة / مهام AI / قائمة البناء)."""

    __tablename__ = "generated_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("project_templates.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=GeneratedProjectStatus.queued)
    zip_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    coupon_type: Mapped[str] = mapped_column(String(16), default=CouponType.percent)
    value: Mapped[float] = mapped_column(Float)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("coupon_id", "user_id"),)


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    source: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AIRequest(Base):
    __tablename__ = "ai_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str] = mapped_column(Text)
    response_summary: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Statistic(Base):
    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10), unique=True)  # YYYY-MM-DD
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    code_generations: Mapped[int] = mapped_column(Integer, default=0)
    files_sold: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
