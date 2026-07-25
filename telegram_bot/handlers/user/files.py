"""
ميزة الملفات البرمجية - عرض الفئات، الملفات، الشراء والتحميل
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import PaymentStatus, User
from database.repository import (
    CodeFileRepository,
    PaymentMethodRepository,
    PaymentRepository,
    PurchaseRepository,
    SettingsRepository,
    StatisticRepository,
)
from keyboards.dynamic import simple_back_keyboard
from locales import get_text
from services.coupon_service import CouponError, validate_and_apply
from services.referral_service import process_referral_reward
from states.user_states import FilePurchaseStates
from utils.helpers import format_money

router = Router(name="files")


@router.callback_query(F.data == "feat:code_files")
async def show_categories(callback: CallbackQuery, session, user: User) -> None:
    repo = CodeFileRepository(session)
    categories = await repo.categories()

    if not categories:
        await callback.message.edit_text(
            get_text(user.language, "no_files_in_category"),
            reply_markup=simple_back_keyboard(user.language),
        )
        await callback.answer()
        return

    rows = [
        [InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"filecat:{cat}")] for cat in categories
    ]
    rows.append([InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="nav:main")])
    await callback.message.edit_text(
        get_text(user.language, "code_files_menu"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filecat:"))
async def list_files_in_category(callback: CallbackQuery, session, user: User) -> None:
    category = callback.data.split(":", 1)[1]
    repo = CodeFileRepository(session)
    files = await repo.list_active(category)

    if not files:
        await callback.answer(get_text(user.language, "no_files_in_category"), show_alert=True)
        return

    rows = [
        [InlineKeyboardButton(
            text=f"📦 {f.title} — {format_money(f.price)}", callback_data=f"fileview:{f.id}"
        )]
        for f in files
    ]
    rows.append([InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="feat:code_files")])
    await callback.message.edit_text(
        get_text(user.language, "code_files_menu"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fileview:"))
async def view_file(callback: CallbackQuery, session, user: User) -> None:
    file_id = int(callback.data.split(":")[1])
    repo = CodeFileRepository(session)
    item = await repo.get(file_id)

    if not item or not item.is_active:
        await callback.answer("⚠️ هذا الملف غير متاح.", show_alert=True)
        return

    purchase_repo = PurchaseRepository(session)
    already_bought = await purchase_repo.has_purchased_file(user.id, file_id)

    text = get_text(
        user.language, "file_details", title=item.title, description=item.description,
        price=format_money(item.price),
    )

    if already_bought:
        await callback.message.answer_document(item.file_id, caption=get_text(user.language, "file_already_purchased"))
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 شراء الآن", callback_data=f"filebuy:{file_id}")],
            [InlineKeyboardButton(text=get_text(user.language, "back"), callback_data=f"filecat:{item.category}")],
        ]
    )

    if item.photo_id:
        await callback.message.answer_photo(item.photo_id, caption=text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data.startswith("filebuy:"))
async def start_file_purchase(callback: CallbackQuery, state: FSMContext, session, user: User) -> None:
    file_id = int(callback.data.split(":")[1])
    repo = CodeFileRepository(session)
    item = await repo.get(file_id)

    if not item:
        await callback.answer("⚠️ هذا الملف غير متاح.", show_alert=True)
        return

    methods_repo = PaymentMethodRepository(session)
    methods = await methods_repo.list_active()

    if not methods:
        await callback.answer("⚠️ لا توجد طرق دفع مفعّلة حاليًا.", show_alert=True)
        return

    await state.update_data(file_id=file_id, price=item.price)

    rows = [
        [InlineKeyboardButton(text=f"{m.name}", callback_data=f"filepay:{m.id}")] for m in methods
    ]
    rows.append([InlineKeyboardButton(text="🎟️ لدي كوبون", callback_data="filecoupon")])
    await callback.message.answer(
        get_text(user.language, "choose_payment_method"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(F.data == "filecoupon")
async def ask_file_coupon(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(FilePurchaseStates.waiting_coupon)
    await callback.message.answer(get_text(user.language, "enter_coupon"))
    await callback.answer()


@router.message(FilePurchaseStates.waiting_coupon)
async def apply_file_coupon(message: Message, state: FSMContext, session, user: User) -> None:
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
    await message.answer(get_text(user.language, "coupon_applied", price=format_money(final_price)))


@router.callback_query(F.data.startswith("filepay:"))
async def choose_file_payment(callback: CallbackQuery, state: FSMContext, session, user: User) -> None:
    method_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    file_id = data.get("file_id")
    price = data.get("price", 0.0)

    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)
    if not method or not file_id:
        await callback.answer("⚠️ حدث خطأ، حاول مجددًا.", show_alert=True)
        return

    await state.update_data(method_id=method_id)
    text = get_text(
        user.language, "payment_instructions", instructions=method.instructions,
        price=price, currency=method.currency,
    )
    await callback.message.answer(text)
    await callback.message.answer(get_text(user.language, "send_proof"))
    await state.set_state(FilePurchaseStates.waiting_payment_proof)
    await callback.answer()


@router.message(FilePurchaseStates.waiting_payment_proof)
async def receive_file_payment_proof(message: Message, state: FSMContext, session, user: User) -> None:
    data = await state.get_data()
    file_id = data.get("file_id")
    method_id = data.get("method_id")
    price = data.get("price", 0.0)

    if not file_id or not method_id:
        return

    proof_file_id = message.photo[-1].file_id if message.photo else None
    reference = message.caption if message.photo else message.text

    payment_repo = PaymentRepository(session)
    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)

    status = PaymentStatus.approved if method and method.code == "stars" else PaymentStatus.pending

    payment = await payment_repo.create(
        user_id=user.id, method_id=method_id, amount=price, purpose=f"file:{file_id}",
        reference=reference, proof_file_id=proof_file_id, status=status,
    )

    if status == PaymentStatus.approved:
        await _deliver_file(message, session, user, file_id, price)
        await state.clear()
    else:
        await message.answer(get_text(user.language, "payment_pending_review"))
        await state.clear()
        for admin_id in await _admin_ids(session):
            try:
                await message.bot.send_message(
                    admin_id, f"💳 طلب شراء ملف #{payment.id}\nالمستخدم: {user.telegram_id}\nالمبلغ: {price}"
                )
            except Exception:
                pass


async def _deliver_file(message: Message, session, user: User, file_id: int, price: float) -> None:
    repo = CodeFileRepository(session)
    item = await repo.get(file_id)
    if not item:
        return

    purchase_repo = PurchaseRepository(session)
    await purchase_repo.create(user.id, "file", file_id, price)
    await repo.increment_downloads(file_id)

    stats_repo = StatisticRepository(session)
    await stats_repo.bump_file_sale(price)
    await process_referral_reward(session, user.id)

    await message.answer_document(item.file_id, caption=f"✅ {item.title}")

    from services.announcer import announce_to_channel

    await announce_to_channel(message.bot, session, f"📦 تم بيع ملف \"{item.title}\" بنجاح بمبلغ {format_money(price)}.")


async def _admin_ids(session) -> list[int]:
    from config import config
    from database.repository import AdminRepository

    admins = await AdminRepository(session).list_all()
    return list({*config.super_admins, *(a.telegram_id for a in admins)})
