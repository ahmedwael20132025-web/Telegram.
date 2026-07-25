"""
لوحة الأدمن: نظام الصفحات الديناميكية وبناء التنقل (Dynamic Pages & Navigation Builder)
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repository import ButtonRepository, PageRepository
from filters.admin_filter import IsAdmin
from keyboards.admin import admin_back_keyboard, paginated_list_keyboard
from locales import SUPPORTED_LANGUAGES
from states.admin_states import AdminButtonStates, AdminPageStates

router = Router(name="admin_pages")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PAGE_SIZE = 6


# ============================================================ الصفحات =====
@router.callback_query(F.data == "adm:pages")
async def list_pages(callback: CallbackQuery, session) -> None:
    await _render_pages_page(callback, session, page=0)


@router.callback_query(F.data.startswith("admpages:page:"))
async def paginate_pages(callback: CallbackQuery, session) -> None:
    page = int(callback.data.split(":")[-1])
    await _render_pages_page(callback, session, page)


async def _render_pages_page(callback: CallbackQuery, session, page: int) -> None:
    repo = PageRepository(session)
    all_pages = await repo.list_all()
    total_pages = max(1, (len(all_pages) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = all_pages[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    items = [
        (f"{'👁️' if p.is_visible else '🚫'} {p.code}", f"admpage:{p.id}") for p in chunk
    ]
    keyboard = paginated_list_keyboard(items, page, total_pages, "admpages", back_callback="adm:main")
    keyboard.inline_keyboard.insert(
        0, [InlineKeyboardButton(text="➕ إنشاء صفحة جديدة", callback_data="admpage_new")]
    )

    await callback.message.edit_text(
        "🧭 <b>الصفحات الديناميكية</b>\n\nاختر صفحة لإدارتها أو أنشئ صفحة جديدة:",
        reply_markup=keyboard, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admpage_new")
async def create_page_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل معرّف الصفحة (بالإنجليزية بدون مسافات)، مثال: about_us")
    await state.set_state(AdminPageStates.waiting_code)
    await callback.answer()


@router.message(AdminPageStates.waiting_code)
async def create_page_code(message: Message, state: FSMContext, session) -> None:
    code = message.text.strip().replace(" ", "_")
    repo = PageRepository(session)
    if await repo.get_by_code(code):
        await message.answer("⚠️ يوجد صفحة بهذا المعرّف بالفعل، أرسل معرّفًا آخر.")
        return

    page = await repo.create(code=code)
    await state.update_data(page_id=page.id, language="ar")
    await message.answer("✍️ أرسل عنوان الصفحة (باللغة العربية):")
    await state.set_state(AdminPageStates.waiting_title)


@router.message(AdminPageStates.waiting_title)
async def create_page_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await message.answer("✍️ أرسل وصفًا مختصرًا للصفحة:")
    await state.set_state(AdminPageStates.waiting_description)


@router.message(AdminPageStates.waiting_description)
async def create_page_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await message.answer("✍️ أرسل النص الكامل للصفحة (يدعم HTML بسيط مثل <b> و <i>):")
    await state.set_state(AdminPageStates.waiting_body)


@router.message(AdminPageStates.waiting_body)
async def create_page_body(message: Message, state: FSMContext) -> None:
    await state.update_data(body_text=message.text)
    await message.answer(
        "📎 أرسل صورة أو فيديو أو ملف مرفق للصفحة الآن، أو أرسل كلمة 'تخطي' للمتابعة بدون وسائط."
    )
    await state.set_state(AdminPageStates.waiting_media)


@router.message(AdminPageStates.waiting_media)
async def create_page_media(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    page_id = data["page_id"]
    repo = PageRepository(session)

    media_fields = {}
    if message.photo:
        media_fields["image_file_id"] = message.photo[-1].file_id
    elif message.video:
        media_fields["video_file_id"] = message.video.file_id
    elif message.document:
        media_fields["document_file_id"] = message.document.file_id

    await repo.upsert_translation(
        page_id, "ar",
        title=data.get("title", ""), description=data.get("description", ""),
        body_text=data.get("body_text", ""), **media_fields,
    )

    await message.answer("✅ تم إنشاء الصفحة بنجاح.", reply_markup=admin_back_keyboard("adm:pages"))
    await state.clear()


@router.callback_query(F.data.startswith("admpage:"))
async def manage_page(callback: CallbackQuery, session) -> None:
    page_id = int(callback.data.split(":")[1])
    repo = PageRepository(session)
    page = await repo.get(page_id)
    if not page:
        await callback.answer("⚠️ الصفحة غير موجودة.", show_alert=True)
        return

    translations = await repo.list_translations(page_id)
    langs = ", ".join(t.language for t in translations) or "لا يوجد"

    text = (
        f"🧭 <b>{page.code}</b>\n"
        f"👁️ ظاهرة: {'نعم' if page.is_visible else 'لا'}\n"
        f"🔐 صلاحية الوصول: {page.access_level}\n"
        f"🌐 اللغات المُترجمة: {langs}"
    )
    rows = [
        [InlineKeyboardButton(text="👁️ إخفاء/إظهار", callback_data=f"admpage_toggle:{page_id}")],
        [InlineKeyboardButton(text="🌐 إضافة/تعديل ترجمة", callback_data=f"admpage_translate:{page_id}")],
        [InlineKeyboardButton(text="🔐 تغيير صلاحية الوصول", callback_data=f"admpage_access:{page_id}")],
        [InlineKeyboardButton(text="🗑️ حذف الصفحة", callback_data=f"admpage_delete:{page_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:pages")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admpage_toggle:"))
async def toggle_page_visibility(callback: CallbackQuery, session) -> None:
    page_id = int(callback.data.split(":")[1])
    repo = PageRepository(session)
    await repo.toggle_visibility(page_id)
    await callback.answer("✅ تم التحديث")
    await manage_page(callback, session)


@router.callback_query(F.data.startswith("admpage_access:"))
async def change_page_access(callback: CallbackQuery, session) -> None:
    page_id = int(callback.data.split(":")[1])
    repo = PageRepository(session)
    page = await repo.get(page_id)
    if not page:
        return
    levels = ["all", "subscribers_only", "admins_only"]
    next_level = levels[(levels.index(page.access_level) + 1) % len(levels)]
    await repo.update_fields(page_id, access_level=next_level)
    await callback.answer(f"✅ صلاحية الوصول الآن: {next_level}")
    await manage_page(callback, session)


@router.callback_query(F.data.startswith("admpage_delete:"))
async def delete_page(callback: CallbackQuery, session) -> None:
    page_id = int(callback.data.split(":")[1])
    repo = PageRepository(session)
    await repo.delete(page_id)
    await callback.answer("🗑️ تم الحذف")
    await _render_pages_page(callback, session, page=0)


@router.callback_query(F.data.startswith("admpage_translate:"))
async def start_translation(callback: CallbackQuery, state: FSMContext) -> None:
    page_id = int(callback.data.split(":")[1])
    rows = [
        [InlineKeyboardButton(text=lang, callback_data=f"admpage_lang:{page_id}:{lang}")]
        for lang in SUPPORTED_LANGUAGES
    ]
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"admpage:{page_id}")])
    await callback.message.edit_text("🌐 اختر اللغة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("admpage_lang:"))
async def choose_translation_language(callback: CallbackQuery, state: FSMContext) -> None:
    _, page_id, lang = callback.data.split(":")
    await state.update_data(page_id=int(page_id), language=lang)
    await callback.message.answer(f"✍️ أرسل عنوان الصفحة باللغة ({lang}):")
    await state.set_state(AdminPageStates.waiting_title)
    await callback.answer()


# ======================================================= الأزرار الديناميكية
@router.callback_query(F.data == "adm:buttons")
async def list_buttons(callback: CallbackQuery, session) -> None:
    await _render_buttons_page(callback, session, page=0)


@router.callback_query(F.data.startswith("admbtns:page:"))
async def paginate_buttons(callback: CallbackQuery, session) -> None:
    page = int(callback.data.split(":")[-1])
    await _render_buttons_page(callback, session, page)


async def _render_buttons_page(callback: CallbackQuery, session, page: int) -> None:
    repo = ButtonRepository(session)
    all_buttons = await repo.list_all("main")
    total_pages = max(1, (len(all_buttons) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = all_buttons[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    items = [
        (f"{'👁️' if b.is_visible else '🚫'} {b.emoji} {b.text}", f"admbtn:{b.id}") for b in chunk
    ]
    keyboard = paginated_list_keyboard(items, page, total_pages, "admbtns", back_callback="adm:main")
    keyboard.inline_keyboard.insert(
        0, [InlineKeyboardButton(text="➕ إنشاء زر جديد", callback_data="admbtn_new")]
    )
    await callback.message.edit_text(
        "🔘 <b>إدارة الأزرار</b>\n\nاختر زرًا لتعديله أو أنشئ زرًا جديدًا:",
        reply_markup=keyboard, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admbtn_new")
async def create_button_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل معرّف الزر (بالإنجليزية، فريد)، مثال: promo_button")
    await state.set_state(AdminButtonStates.waiting_code)
    await callback.answer()


@router.message(AdminButtonStates.waiting_code)
async def create_button_code(message: Message, state: FSMContext, session) -> None:
    code = message.text.strip().replace(" ", "_")
    repo = ButtonRepository(session)
    if await repo.get_by_code(code):
        await message.answer("⚠️ يوجد زر بهذا المعرّف بالفعل.")
        return
    await state.update_data(code=code)
    await message.answer("✍️ أرسل نص الزر:")
    await state.set_state(AdminButtonStates.waiting_text)


@router.message(AdminButtonStates.waiting_text)
async def create_button_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text.strip())
    await message.answer("😀 أرسل الإيموجي المرافق للزر (أو أرسل - لتجاهله):")
    await state.set_state(AdminButtonStates.waiting_emoji)


@router.message(AdminButtonStates.waiting_emoji)
async def create_button_emoji(message: Message, state: FSMContext) -> None:
    emoji = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(emoji=emoji)
    rows = [
        [InlineKeyboardButton(text="🧩 صفحة ديناميكية", callback_data="admbtn_type:page")],
        [InlineKeyboardButton(text="🔗 رابط خارجي", callback_data="admbtn_type:url")],
        [InlineKeyboardButton(text="📢 قناة تيليجرام", callback_data="admbtn_type:channel")],
        [InlineKeyboardButton(text="⚙️ ميزة مدمجة", callback_data="admbtn_type:feature")],
        [InlineKeyboardButton(text="🧷 إجراء مخصص", callback_data="admbtn_type:custom")],
    ]
    await message.answer("اختر نوع الإجراء عند الضغط على الزر:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(AdminButtonStates.waiting_action_type)


@router.callback_query(AdminButtonStates.waiting_action_type, F.data.startswith("admbtn_type:"))
async def choose_button_action_type(callback: CallbackQuery, state: FSMContext) -> None:
    action_type = callback.data.split(":")[1]
    await state.update_data(action_type=action_type)

    prompts = {
        "page": "✍️ أرسل معرّف الصفحة (code) التي سيفتحها الزر:",
        "url": "✍️ أرسل الرابط الخارجي (https://...):",
        "channel": "✍️ أرسل معرّف القناة (ID) المُسجّلة مسبقًا في قسم الاشتراك الإجباري:",
        "feature": "✍️ أرسل اسم الميزة (مثال: wallet, referral, generate_code, code_files, support, language, bot_channel):",
        "custom": "✍️ أرسل معرّف الإجراء المخصص (سيُستخدم لاحقًا مع نص في الإعدادات باسم custom_action_<المعرّف>):",
    }
    await callback.message.answer(prompts[action_type])
    await state.set_state(AdminButtonStates.waiting_target)
    await callback.answer()


@router.message(AdminButtonStates.waiting_target)
async def create_button_target(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    repo = ButtonRepository(session)

    all_buttons = await repo.list_all("main")
    sort_order = len(all_buttons)

    await repo.create(
        code=data["code"], text=data["text"], emoji=data.get("emoji", ""),
        action_type=data["action_type"], target=message.text.strip(),
        sort_order=sort_order, menu="main",
    )
    await message.answer("✅ تم إنشاء الزر بنجاح.", reply_markup=admin_back_keyboard("adm:buttons"))
    await state.clear()


@router.callback_query(F.data.startswith("admbtn:"))
async def manage_button(callback: CallbackQuery, session) -> None:
    button_id = int(callback.data.split(":")[1])
    repo = ButtonRepository(session)
    button = await repo.get(button_id)
    if not button:
        await callback.answer("⚠️ الزر غير موجود.", show_alert=True)
        return

    text = (
        f"🔘 <b>{button.emoji} {button.text}</b>\n"
        f"النوع: {button.action_type}\nالهدف: {button.target or button.url or button.feature}\n"
        f"الترتيب: {button.sort_order}\n👁️ ظاهر: {'نعم' if button.is_visible else 'لا'}"
    )
    rows = [
        [InlineKeyboardButton(text="👁️ إخفاء/إظهار", callback_data=f"admbtn_toggle:{button_id}")],
        [InlineKeyboardButton(text="⬆️ نقل لأعلى", callback_data=f"admbtn_up:{button_id}"),
         InlineKeyboardButton(text="⬇️ نقل لأسفل", callback_data=f"admbtn_down:{button_id}")],
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admbtn_delete:{button_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:buttons")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admbtn_toggle:"))
async def toggle_button_visibility(callback: CallbackQuery, session) -> None:
    button_id = int(callback.data.split(":")[1])
    repo = ButtonRepository(session)
    button = await repo.get(button_id)
    if button:
        await repo.update_fields(button_id, is_visible=not button.is_visible)
    await callback.answer("✅ تم التحديث")
    await manage_button(callback, session)


@router.callback_query(F.data.startswith("admbtn_delete:"))
async def delete_button(callback: CallbackQuery, session) -> None:
    button_id = int(callback.data.split(":")[1])
    repo = ButtonRepository(session)
    await repo.delete(button_id)
    await callback.answer("🗑️ تم الحذف")
    await _render_buttons_page(callback, session, page=0)


@router.callback_query(F.data.startswith("admbtn_up:"))
async def move_button_up(callback: CallbackQuery, session) -> None:
    await _reorder_button(callback, session, direction=-1)


@router.callback_query(F.data.startswith("admbtn_down:"))
async def move_button_down(callback: CallbackQuery, session) -> None:
    await _reorder_button(callback, session, direction=1)


async def _reorder_button(callback: CallbackQuery, session, direction: int) -> None:
    button_id = int(callback.data.split(":")[1])
    repo = ButtonRepository(session)
    all_buttons = await repo.list_all("main")
    ids = [b.id for b in all_buttons]

    if button_id not in ids:
        await callback.answer()
        return

    index = ids.index(button_id)
    new_index = index + direction
    if 0 <= new_index < len(ids):
        ids[index], ids[new_index] = ids[new_index], ids[index]
        await repo.reorder(ids)

    await callback.answer("✅ تم إعادة الترتيب")
    await manage_button(callback, session)
