"""
ميزة المحفظة (Wallet) - عرض الرصيد وطلب السحب
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import User, WalletOpType
from database.repository import SettingsRepository, UserRepository, WithdrawRepository
from locales import get_text
from states.user_states import WalletStates
from utils.helpers import format_money, is_valid_amount

router = Router(name="wallet")


@router.callback_query(F.data == "feat:wallet")
async def show_wallet(callback: CallbackQuery, session, user: User) -> None:
    text = get_text(user.language, "wallet_balance", balance=format_money(user.wallet_balance))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💸 طلب سحب", callback_data="wallet:withdraw")],
            [InlineKeyboardButton(text=get_text(user.language, "back"), callback_data="nav:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "wallet:withdraw")
async def ask_withdraw_amount(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.message.edit_text(get_text(user.language, "withdraw_ask_amount"))
    await state.set_state(WalletStates.waiting_withdraw_amount)
    await callback.answer()


@router.message(WalletStates.waiting_withdraw_amount)
async def receive_withdraw_amount(message: Message, state: FSMContext, session, user: User) -> None:
    if not is_valid_amount(message.text):
        await message.answer("⚠️ الرجاء إدخال مبلغ صحيح.")
        return

    amount = float(message.text.strip())
    settings_repo = SettingsRepository(session)
    min_amount = await settings_repo.get_float("min_withdraw_amount", 20)

    if amount < min_amount:
        await message.answer(f"⚠️ الحد الأدنى للسحب هو {format_money(min_amount)}")
        return

    if amount > user.wallet_balance:
        await message.answer(get_text(user.language, "withdraw_insufficient"))
        return

    await state.update_data(amount=amount)
    await message.answer(get_text(user.language, "withdraw_ask_details"))
    await state.set_state(WalletStates.waiting_withdraw_details)


@router.message(WalletStates.waiting_withdraw_details)
async def receive_withdraw_details(message: Message, state: FSMContext, session, user: User) -> None:
    data = await state.get_data()
    amount = data.get("amount", 0.0)

    if amount > user.wallet_balance:
        await message.answer(get_text(user.language, "withdraw_insufficient"))
        await state.clear()
        return

    user_repo = UserRepository(session)
    await user_repo.adjust_wallet(user, -amount, WalletOpType.withdraw, note="طلب سحب")

    withdraw_repo = WithdrawRepository(session)
    request = await withdraw_repo.create(user.id, amount, message.text.strip())

    await message.answer(get_text(user.language, "withdraw_submitted"))

    for admin_id in await _admin_ids(session):
        try:
            await message.bot.send_message(
                admin_id,
                f"💸 طلب سحب جديد #{request.id}\nالمستخدم: {user.telegram_id}\nالمبلغ: {amount}\nالبيانات: {message.text.strip()}",
            )
        except Exception:
            pass

    await state.clear()


async def _admin_ids(session) -> list[int]:
    from config import config
    from database.repository import AdminRepository

    admins = await AdminRepository(session).list_all()
    return list({*config.super_admins, *(a.telegram_id for a in admins)})
