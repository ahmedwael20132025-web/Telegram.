"""
ميزة إنشاء الأكواد عبر الذكاء الاصطناعي
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import PaymentStatus, User, WalletOpType
from database.repository import (
    AIRequestRepository,
    PaymentMethodRepository,
    PaymentRepository,
    PurchaseRepository,
    SettingsRepository,
    StatisticRepository,
    UserRepository,
)
from keyboards.dynamic import simple_back_keyboard
from locales import get_text
from services.ai_service import AIGenerationError, AIService
from services.code_packager import build_project_zip
from services.coupon_service import CouponError, validate_and_apply
from services.referral_service import process_referral_reward
from services.vip_service import get_vip_status
from states.user_states import CodeGenerationStates

router = Router(name="code_generation")


@router.callback_query(F.data == "feat:generate_code")
async def start_generation(callback: CallbackQuery, state: FSMContext, session, user: User) -> None:
    is_vip, _ = await get_vip_status(session, user.id)

    if is_vip or user.free_credits > 0:
        prompt_text = get_text(user.language, "ask_project_description")
        if is_vip:
            prompt_text = "👑 عضويتك VIP تمنحك إنشاءً غير محدود.\n\n" + prompt_text
        await callback.message.edit_text(
            prompt_text,
            reply_markup=simple_back_keyboard(user.language),
        )
        await state.set_state(CodeGenerationStates.waiting_description)
        await state.update_data(paid=False)
        await callback.answer()
        return

    settings_repo = SettingsRepository(session)
    price = await settings_repo.get_float("code_generation_price", 10)
    methods_repo = PaymentMethodRepository(session)
    methods = await methods_repo.list_active()

    if not methods:
        await callback.answer("⚠️ لا توجد طرق دفع مفعّلة حاليًا.", show_alert=True)
        return

    rows = [
        [InlineKeyboardButton(text=f"{m.name} — {price} {m.currency}", callback_data=f"gen_pay:{m.id}")]
        for m in methods
    ]
    rows.append([InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="nav:main")])

    await callback.message.edit_text(
        get_text(user.language, "no_credits") + "\n\n" + get_text(user.language, "choose_payment_method"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gen_pay:"))
async def choose_payment_method(callback: CallbackQuery, state: FSMContext, session, user: User) -> None:
    method_id = int(callback.data.split(":")[1])
    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)
    if not method:
        await callback.answer("⚠️ طريقة الدفع غير متاحة.", show_alert=True)
        return

    settings_repo = SettingsRepository(session)
    price = await settings_repo.get_float("code_generation_price", 10)

    await state.update_data(method_id=method_id, price=price, purpose="code_generation")

    if method.code == "stars":
        rows = [
            [InlineKeyboardButton(text="🎟️ " + get_text(user.language, "enter_coupon"), callback_data="gen_coupon")],
            [InlineKeyboardButton(text="⭐ ادفع الآن عبر Telegram Stars", callback_data="gen_pay_stars")],
            [InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="feat:generate_code")],
        ]
        await callback.message.edit_text(
            f"⭐ السعر: {int(price)} نجمة (Stars)\nيمكنك استخدام كوبون خصم قبل الدفع، ثم اضغط زر الدفع.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    text = get_text(
        user.language, "payment_instructions",
        instructions=method.instructions, price=price, currency=method.currency,
    )
    rows = [
        [InlineKeyboardButton(text="🎟️ " + get_text(user.language, "enter_coupon"), callback_data="gen_coupon")],
        [InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="feat:generate_code")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(CodeGenerationStates.waiting_payment_proof)
    await callback.answer()
    await callback.message.answer(get_text(user.language, "send_proof"))


@router.callback_query(F.data == "gen_pay_stars")
async def pay_via_stars(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    data = await state.get_data()
    price = data.get("price", 10)

    from services.stars_payment import send_stars_invoice

    await send_stars_invoice(
        callback.bot, callback.from_user.id,
        title="إنشاء كود برمجي", description="دفع لإنشاء كود برمجي عبر الذكاء الاصطناعي",
        payload=f"codegen:{user.id}", amount_stars=int(price),
    )
    await callback.answer()


@router.callback_query(F.data == "gen_coupon")
async def ask_coupon(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(CodeGenerationStates.waiting_coupon)
    await callback.message.answer(get_text(user.language, "enter_coupon"))
    await callback.answer()


@router.message(CodeGenerationStates.waiting_coupon)
async def apply_coupon(message: Message, state: FSMContext, session, user: User) -> None:
    data = await state.get_data()
    price = data.get("price", 0.0)
    try:
        coupon, final_price = await validate_and_apply(session, message.text, user.id, price)
    except CouponError as exc:
        await message.answer(f"❌ {exc}")
        return

    from database.repository import CouponRepository

    await CouponRepository(session).register_usage(coupon, user.id)
    await state.update_data(price=final_price)
    await message.answer(get_text(user.language, "coupon_applied", price=final_price))
    await state.set_state(CodeGenerationStates.waiting_payment_proof)


@router.message(CodeGenerationStates.waiting_payment_proof)
async def receive_payment_proof(message: Message, state: FSMContext, session, user: User) -> None:
    data = await state.get_data()
    method_id = data.get("method_id")
    price = data.get("price", 0.0)

    if not method_id:
        return

    proof_file_id = None
    reference = message.text
    if message.photo:
        proof_file_id = message.photo[-1].file_id
        reference = message.caption or ""

    payment_repo = PaymentRepository(session)
    method_repo = PaymentMethodRepository(session)
    method = await method_repo.get(method_id)

    status = PaymentStatus.pending
    if method and method.code == "stars":
        status = PaymentStatus.approved  # يُفترض التأكيد التلقائي عبر Stars

    payment = await payment_repo.create(
        user_id=user.id,
        method_id=method_id,
        amount=price,
        purpose="code_generation",
        reference=reference,
        proof_file_id=proof_file_id,
        status=status,
    )

    if status == PaymentStatus.approved:
        await message.answer(get_text(user.language, "payment_approved"))
        await message.answer(get_text(user.language, "ask_project_description"))
        await state.set_state(CodeGenerationStates.waiting_description)
        await state.update_data(paid=True, payment_id=payment.id)
    else:
        await message.answer(get_text(user.language, "payment_pending_review"))
        await state.clear()
        for admin_id in await _admin_ids(session):
            try:
                await message.bot.send_message(
                    admin_id,
                    f"💳 طلب دفع جديد #{payment.id}\nالمستخدم: {user.telegram_id}\nالمبلغ: {price}",
                )
            except Exception:
                pass


async def _admin_ids(session) -> list[int]:
    from config import config
    from database.repository import AdminRepository

    admins = await AdminRepository(session).list_all()
    return list({*config.super_admins, *(a.telegram_id for a in admins)})


@router.message(CodeGenerationStates.waiting_description)
async def generate_code_handler(message: Message, state: FSMContext, session, user: User) -> None:
    data = await state.get_data()
    prompt = message.text.strip()

    if not prompt:
        return

    status_msg = await message.answer(get_text(user.language, "generating_code"))

    settings_repo = SettingsRepository(session)
    provider = await settings_repo.get("default_ai_provider", "claude")
    ai_service = AIService(provider)

    ai_repo = AIRequestRepository(session)
    stats_repo = StatisticRepository(session)
    user_repo = UserRepository(session)

    try:
        response = await ai_service.generate(prompt)
        await ai_repo.create(user.id, provider, prompt, response[:500], success=True)
    except AIGenerationError as exc:
        await ai_repo.create(user.id, provider, prompt, str(exc), success=False)
        await status_msg.edit_text(f"❌ حدث خطأ أثناء إنشاء الكود: {exc}")
        await state.clear()
        return

    if not data.get("paid"):
        await user_repo.decrement_free_credit(user)
    else:
        purchase_repo = PurchaseRepository(session)
        await purchase_repo.create(user.id, "code_generation", None, data.get("price", 0.0))
        await stats_repo.add_revenue(data.get("price", 0.0))
        await process_referral_reward(session, user.id)

    await stats_repo.bump_code_generation()
    await status_msg.delete()

    from services.announcer import announce_to_channel

    await announce_to_channel(
        message.bot, session,
        f"🧠 تم إنشاء كود جديد بنجاح بواسطة أحد المستخدمين. (طلب رقم #{await ai_repo.count_total()})",
    )

    # إرسال الرد نصيًا (مقسّمًا إذا كان طويلاً) - وإرفاق ZIP إذا احتوى على أكواد متعددة
    request_id = await ai_repo.count_total()
    zip_file = build_project_zip(request_id, response)

    for chunk_start in range(0, len(response), 3500):
        chunk = response[chunk_start: chunk_start + 3500]
        await message.answer(chunk)

    if zip_file:
        await message.answer_document(FSInputFile(zip_file), caption="📦 ملفات مشروعك جاهزة")

    await state.clear()
