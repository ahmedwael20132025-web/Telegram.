"""
حالات لوحة الأدمن (FSM States)
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminBroadcastStates(StatesGroup):
    waiting_content = State()


class AdminFileStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_category = State()
    waiting_price = State()
    waiting_file = State()
    waiting_photo = State()
    editing_field = State()


class AdminChannelStates(StatesGroup):
    waiting_chat_id = State()
    waiting_title = State()
    waiting_link = State()


class AdminPaymentMethodStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_instructions = State()
    editing_field = State()


class AdminButtonStates(StatesGroup):
    waiting_code = State()
    waiting_text = State()
    waiting_emoji = State()
    waiting_action_type = State()
    waiting_target = State()
    editing_field = State()


class AdminPageStates(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_description = State()
    waiting_body = State()
    waiting_media = State()
    editing_field = State()


class AdminCouponStates(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_max_uses = State()
    waiting_expiry = State()


class AdminSettingStates(StatesGroup):
    waiting_value = State()


class AdminUserStates(StatesGroup):
    waiting_search_id = State()
    waiting_balance_amount = State()


class AdminApiKeyStates(StatesGroup):
    waiting_claude_key = State()
    waiting_openai_key = State()
    waiting_google_key = State()


class AdminVipStates(StatesGroup):
    waiting_name = State()
    waiting_badge = State()
    waiting_description = State()
    waiting_features = State()
    waiting_price = State()
    waiting_duration = State()
    editing_field = State()
