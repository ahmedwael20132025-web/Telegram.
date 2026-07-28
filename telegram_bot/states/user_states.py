"""
حالات المستخدم (FSM States)
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CodeGenerationStates(StatesGroup):
    waiting_description = State()
    waiting_payment_proof = State()
    waiting_coupon = State()


class WalletStates(StatesGroup):
    waiting_withdraw_amount = State()
    waiting_withdraw_details = State()


class FilePurchaseStates(StatesGroup):
    waiting_payment_proof = State()
    waiting_coupon = State()


class VipStates(StatesGroup):
    waiting_payment_proof = State()


class ProjectGeneratorStates(StatesGroup):
    choosing_template = State()
    waiting_description = State()
    collecting_variable = State()
    waiting_existing_project = State()
    waiting_payment_proof = State()
