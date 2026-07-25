"""
لوحة الأدمن: مكتبة قوالب المشاريع، والمشاريع المولّدة (مهام AI / قائمة البناء)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repository import GeneratedProjectRepository, ProjectTemplateRepository
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard

router = Router(name="admin_project_generator")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

DEFAULT_TEMPLATES = [
    dict(code="telegram_store", name="🛒 متجر تيليجرام", prompt_prefix="أنشئ بوت متجر إلكتروني كامل على تيليجرام يدعم عرض المنتجات والسلة والدفع."),
    dict(code="ai_bot", name="🤖 بوت ذكاء اصطناعي", prompt_prefix="أنشئ بوت محادثة يعتمد على نموذج ذكاء اصطناعي للرد على استفسارات المستخدمين."),
    dict(code="file_store", name="📂 متجر ملفات", prompt_prefix="أنشئ بوت لبيع الملفات الرقمية مع نظام دفع وتحميل آمن."),
    dict(code="admin_panel", name="🛠️ لوحة تحكم", prompt_prefix="أنشئ بوت إداري بلوحة تحكم كاملة لإدارة مستخدمين ومحتوى."),
    dict(code="ticket_bot", name="🎫 بوت تذاكر دعم", prompt_prefix="أنشئ بوت لإدارة تذاكر الدعم الفني مع تصنيف وأولويات."),
    dict(code="support_bot", name="🆘 بوت دعم فني", prompt_prefix="أنشئ بوت رد آلي على استفسارات الدعم الفني الشائعة."),
    dict(code="music_bot", name="🎵 بوت موسيقى", prompt_prefix="أنشئ بوت بحث وتشغيل مقاطع موسيقية."),
    dict(code="downloader", name="⬇️ بوت تحميل", prompt_prefix="أنشئ بوت لتحميل الوسائط من الروابط التي يرسلها المستخدم."),
    dict(code="crm", name="📇 نظام CRM", prompt_prefix="أنشئ بوت لإدارة علاقات العملاء ومتابعة المبيعات."),
    dict(code="moderation", name="🛡️ بوت إشراف", prompt_prefix="أنشئ بوت لإدارة والإشراف على مجموعات تيليجرام."),
    dict(code="economy", name="💹 بوت اقتصادي", prompt_prefix="أنشئ بوت لعبة اقتصادية داخل تيليجرام بعملة افتراضية."),
    dict(code="games", name="🎮 بوت ألعاب", prompt_prefix="أنشئ بوت ألعاب تفاعلية بسيطة داخل تيليجرام."),
]


@router.callback_query(F.data == "adm:templates")
async def list_templates(callback: CallbackQuery, session) -> None:
    repo = ProjectTemplateRepository(session)
    templates = await repo.list_all()

    if not templates:
        for tpl in DEFAULT_TEMPLATES:
            await repo.create(**tpl, sort_order=DEFAULT_TEMPLATES.index(tpl))
        templates = await repo.list_all()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if t.is_active else '🚫'} {t.name}", callback_data=f"tpl_adm:{t.id}"
        )]
        for t in templates
    ]
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])
    await callback.message.edit_text("🧱 مكتبة قوالب المشاريع", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("tpl_adm:"))
async def manage_template(callback: CallbackQuery, session) -> None:
    template_id = int(callback.data.split(":")[1])
    repo = ProjectTemplateRepository(session)
    template = await repo.get(template_id)
    if not template:
        await callback.answer("⚠️ غير موجود.", show_alert=True)
        return

    text = f"🧱 <b>{template.name}</b>\n{template.description or template.prompt_prefix}"
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"tpl_toggle:{template_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:templates")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("tpl_toggle:"))
async def toggle_template(callback: CallbackQuery, session) -> None:
    template_id = int(callback.data.split(":")[1])
    repo = ProjectTemplateRepository(session)
    await repo.toggle(template_id)
    await callback.answer("✅ تم التحديث")
    await manage_template(callback, session)


@router.callback_query(F.data == "adm:generated")
async def list_generated_projects(callback: CallbackQuery, session) -> None:
    repo = GeneratedProjectRepository(session)
    projects = await repo.list_recent(15)

    completed = await repo.count_by_status("completed")
    failed = await repo.count_by_status("failed")
    queued = await repo.count_by_status("queued")

    lines = [
        f"• #{p.id} — {p.status} — {p.description[:40]}" for p in projects
    ]
    text = (
        f"🗂️ <b>المشاريع المولّدة (AI Jobs / Build Queue)</b>\n\n"
        f"✅ مكتملة: {completed} | ❌ فاشلة: {failed} | ⏳ قيد الانتظار: {queued}\n\n"
        + "\n".join(lines)
    )
    await callback.message.edit_text(text[:4000], reply_markup=admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()
