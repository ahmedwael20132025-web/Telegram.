"""
دوال مساعدة عامة
"""
from __future__ import annotations

import re


def format_money(amount: float, currency: str = "") -> str:
    formatted = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{formatted} {currency}".strip()


def is_valid_amount(text: str) -> bool:
    try:
        value = float(text.strip())
        return value > 0
    except ValueError:
        return False


def is_valid_channel_id(text: str) -> bool:
    text = text.strip()
    return bool(re.match(r"^(-100\d+|@[\w\d_]+)$", text))


def truncate(text: str, length: int = 200) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
