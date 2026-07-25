"""
لوحات المفاتيح - بما فيها نظام القوائم الديناميكي (Dynamic Navigation Builder)
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import ButtonConfig, Page
from database.repository import ButtonRepository, PageRepository
from locales import get_text


def _button_callback(button: ButtonConfig) -> str | None:
    """يبني الـ callback_data المناسب حسب نوع الإجراء، أو يعيد None إذا كان رابطًا مباشرًا."""
    if button.action_type == "url":
        return None  # سيُستخدم كـ url في InlineKeyboardButton مباشرة
    if button.action_type == "page":
        return f"page:{button.target}"
    if button.action_type == "channel":
        return None  # رابط أيضًا (نعرض invite_link كـ url)
    if button.action_type == "custom":
        return f"custom:{button.target}"
    # feature (الافتراضي - توافق قديم)
    return f"feat:{button.target or button.feature}"


async def build_menu_keyboard(
    session, menu: str = "main", parent_code: str | None = None, columns: int = 2
) -> InlineKeyboardMarkup:
    """يبني كيبورد أي قائمة (رئيسية / صفحة فرعية) بشكل ديناميكي بالكامل من قاعدة البيانات."""
    button_repo = ButtonRepository(session)
    channel_repo = None

    if parent_code:
        buttons = await button_repo.list_visible_children(parent_code)
    else:
        buttons = await button_repo.list_visible(menu)

    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for button in buttons:
        label = f"{button.emoji} {button.text}".strip()

        if button.action_type == "url":
            kb_button = InlineKeyboardButton(text=label, url=button.target or button.url or "https://t.me")
        elif button.action_type == "channel":
            from database.repository import ChannelRepository

            channel_repo = channel_repo or ChannelRepository(session)
            channel = await channel_repo.get(int(button.target)) if button.target.isdigit() else None
            url = channel.invite_link if channel else (button.url or "https://t.me")
            kb_button = InlineKeyboardButton(text=label, url=url)
        else:
            kb_button = InlineKeyboardButton(text=label, callback_data=_button_callback(button))

        current_row.append(kb_button)
        if len(current_row) >= columns:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_page_navigation_keyboard(
    page_buttons_markup: InlineKeyboardMarkup | None, lang: str, back_callback: str = "nav:main"
) -> InlineKeyboardMarkup:
    """يضيف زر رجوع أسفل أزرار الصفحة الديناميكية."""
    rows = list(page_buttons_markup.inline_keyboard) if page_buttons_markup else []
    rows.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def simple_back_keyboard(lang: str, callback: str = "nav:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data=callback)]]
    )


def confirm_cancel_keyboard(lang: str, confirm_cb: str, cancel_cb: str = "nav:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅", callback_data=confirm_cb)],
            [InlineKeyboardButton(text=get_text(lang, "cancel"), callback_data=cancel_cb)],
        ]
    )
