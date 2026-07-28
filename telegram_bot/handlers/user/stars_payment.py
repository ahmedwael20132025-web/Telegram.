"""
الدفع الرسمي عبر Telegram Stars: إرسال فاتورة حقيقية (Invoice) بدل تعليمات نصية،
واستقبال تأكيد الدفع الرسمي من تيليجرام مباشرة (pre_checkout_query + successful_payment).
"""
from __future__ import annotations

from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from database.models import PaymentStatus
from database.repository import (
    CodeFileRepository,
    PaymentMethodRepository,
    PaymentRepository,
    PurchaseRepository,
    StatisticRepository,
    VipPlanRepository,
)
from services.announcer import announce_to_channel
from services.referral_service import process_referral_reward
from services.vip_service import activate_subscription

router = Router(name="stars_payment")


async def send_stars_invoice(
    bot: Bot, chat_id: int, title: str, description: str, payload: str, amount_stars: int
) -> None:
    """يرسل فاتورة دفع رسمية بنجوم تيليجرام (Telegram Stars) مباشرة داخل المحادثة."""
    await bot.send_invoice(
        chat_id=chat_id,
        title=title[:32] or "دفع",
        description=description[:255] or "عملية دفع داخل البوت",
        payload=payload,
        provider_token="",  # فارغ إلزاميًا عند الدفع بنجوم تيليجرام (XTR)
        currency="XTR",
        prices=[LabeledPrice(label=title[:32] or "الإجمالي", amount=max(1, int(amount_stars)))],
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    if ":" not in pre_checkout_query.invoice_payload:
        await pre_checkout_query.answer(ok=False, error_message="طلب دفع غير صالح.")
        return
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, session, user, state: FSMContext) -> None:
    payload = message.successful_payment.invoice_payload
    amount_stars = message.successful_payment.total_amount  # بالـ XTR: 1 وحدة = 1 نجمة

    parts = payload.split(":")
    purpose = parts[0]

    payment_repo = PaymentRepository(session)
    methods_repo = PaymentMethodRepository(session)
    stars_method = await methods_repo.get_by_code("stars")
    method_id = stars_method.id if stars_method else 0

    await payment_repo.create(
        user_id=user.id, method_id=method_id, amount=float(amount_stars),
        purpose=payload, reference=payload, status=PaymentStatus.approved,
    )

    stats_repo = StatisticRepository(session)

    if purpose == "codegen":
        await stats_repo.add_revenue(amount_stars)
        await process_referral_reward(session, user.id)
        await message.answer("✅ تم الدفع بنجاح عبر Telegram Stars! أرسل الآن وصف المشروع.")
        await announce_to_channel(message.bot, session, "🧠 تم تأكيد دفعة إنشاء كود عبر Stars.")

        from states.user_states import CodeGenerationStates

        await state.update_data(paid=True)
        await state.set_state(CodeGenerationStates.waiting_description)

    elif purpose == "file":
        file_id = int(parts[1])
        file_repo = CodeFileRepository(session)
        purchase_repo = PurchaseRepository(session)
        item = await file_repo.get(file_id)

        await purchase_repo.create(user.id, "file", file_id, amount_stars)
        await file_repo.increment_downloads(file_id)
        await stats_repo.bump_file_sale(amount_stars)
        await process_referral_reward(session, user.id)

        if item:
            await message.answer_document(item.file_id, caption=f"✅ {item.title}")
        await announce_to_channel(message.bot, session, "📦 تم بيع ملف بنجاح عبر Stars.")

    elif purpose == "vip":
        plan_id = int(parts[1])
        plan_repo = VipPlanRepository(session)
        plan = await plan_repo.get(plan_id)
        if plan:
            await activate_subscription(session, user.id, plan)
            await message.answer(f"✅ تم تفعيل اشتراكك في {plan.badge} {plan.name} بنجاح عبر Stars!")
            await announce_to_channel(message.bot, session, f"👑 اشتراك VIP جديد ({plan.name}) عبر Stars.")

    elif purpose == "projectgen":
        await stats_repo.add_revenue(amount_stars)
        await message.answer("✅ تم الدفع بنجاح! أرسل الآن وصف المشروع لإنشائه.")
        await announce_to_channel(message.bot, session, "🧱 تم تأكيد دفعة مولّد مشاريع عبر Stars.")

        from states.user_states import ProjectGeneratorStates

        await state.update_data(paid=True, editing_existing=False)
        await state.set_state(ProjectGeneratorStates.waiting_description)
