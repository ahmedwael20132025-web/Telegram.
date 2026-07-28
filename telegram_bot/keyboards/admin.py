"""
لوحات مفاتيح لوحة التحكم الإدارية
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="adm:stats"),
         InlineKeyboardButton(text="👥 المستخدمون", callback_data="adm:users")],
        [InlineKeyboardButton(text="💰 الأرباح", callback_data="adm:revenue"),
         InlineKeyboardButton(text="🎁 الإحالات", callback_data="adm:referrals")],
        [InlineKeyboardButton(text="📂 الملفات البرمجية", callback_data="adm:files"),
         InlineKeyboardButton(text="💳 طرق الدفع", callback_data="adm:payments")],
        [InlineKeyboardButton(text="⭐ أسعار وكوبونات", callback_data="adm:pricing"),
         InlineKeyboardButton(text="📢 الاشتراك الإجباري", callback_data="adm:channels")],
        [InlineKeyboardButton(text="📣 إذاعة", callback_data="adm:broadcast"),
         InlineKeyboardButton(text="🔘 إدارة الأزرار", callback_data="adm:buttons")],
        [InlineKeyboardButton(text="🧭 الصفحات الديناميكية", callback_data="adm:pages"),
         InlineKeyboardButton(text="⚙ الإعدادات", callback_data="adm:settings")],
        [InlineKeyboardButton(text="🤖 مزود الذكاء الاصطناعي", callback_data="adm:ai_provider"),
         InlineKeyboardButton(text="🔑 API Keys", callback_data="adm:api_keys")],
        [InlineKeyboardButton(text="💸 طلبات السحب", callback_data="adm:withdrawals"),
         InlineKeyboardButton(text="📈 السجلات", callback_data="adm:logs")],
        [InlineKeyboardButton(text="💾 النسخ الاحتياطي", callback_data="adm:backup"),
         InlineKeyboardButton(text="🚫 حظر/فك حظر", callback_data="adm:ban")],
        [InlineKeyboardButton(text="🧱 قوالب المشاريع", callback_data="adm:templates"),
         InlineKeyboardButton(text="🗂️ المشاريع المولّدة", callback_data="adm:generated")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_back_keyboard(callback: str = "adm:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data=callback)]]
    )


def paginated_list_keyboard(
    items: list[tuple[str, str]],
    page: int,
    total_pages: int,
    list_prefix: str,
    back_callback: str = "adm:main",
    columns: int = 1,
) -> InlineKeyboardMarkup:
    """
    items: قائمة من (نص الزر, callback_data) لعناصر الصفحة الحالية.
    list_prefix: يُستخدم لبناء أزرار التنقل بين الصفحات (list_prefix:page:N)
    """
    rows: list[list[InlineKeyboardButton]] = []
    current_row = []
    for text, cb in items:
        current_row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(current_row) >= columns:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{list_prefix}:page:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{list_prefix}:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def toggle_row(label_on: str, label_off: str, is_on: bool, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label_on if is_on else label_off, callback_data=callback)
