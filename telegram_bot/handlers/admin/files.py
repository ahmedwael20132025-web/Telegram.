"""
لوحة الأدمن: إدارة الملفات البرمجية المعروضة للبيع
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repository import CodeFileRepository
from filters.admin_filter import IsAdmin
from states.admin_states import AdminFileStates
from utils.helpers import is_valid_amount

router = Router(name="admin_files")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:files")
async def list_files(callback: CallbackQuery, session) -> None:
    repo = CodeFileRepository(session)
    files = await repo.list_all()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if f.is_active else '🚫'} {f.title} ({f.downloads}⬇️)", callback_data=f"file_adm:{f.id}"
        )]
        for f in files[:20]
    ]
    rows.append([InlineKeyboardButton(text="➕ إضافة ملف", callback_data="file_new")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])

    await callback.message.edit_text("📂 الملفات البرمجية", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "file_new")
async def create_file_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("✍️ أرسل عنوان الملف:")
    await state.set_state(AdminFileStates.waiting_title)
    await callback.answer()


@router.message(AdminFileStates.waiting_title)
async def file_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await message.answer("📝 أرسل وصف الملف:")
    await state.set_state(AdminFileStates.waiting_description)


@router.message(AdminFileStates.waiting_description)
async def file_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await message.answer("📁 أرسل اسم الفئة (Category):")
    await state.set_state(AdminFileStates.waiting_category)


@router.message(AdminFileStates.waiting_category)
async def file_category(message: Message, state: FSMContext) -> None:
    await state.update_data(category=message.text.strip())
    await message.answer("💰 أرسل سعر الملف:")
    await state.set_state(AdminFileStates.waiting_price)


@router.message(AdminFileStates.waiting_price)
async def file_price(message: Message, state: FSMContext) -> None:
    if not is_valid_amount(message.text):
        await message.answer("⚠️ أرسل رقمًا صحيحًا.")
        return
    await state.update_data(price=float(message.text.strip()))
    await message.answer("📎 أرسل الآن ملف الكود (Document):")
    await state.set_state(AdminFileStates.waiting_file)


@router.message(AdminFileStates.waiting_file, F.document)
async def file_document(message: Message, state: FSMContext) -> None:
    await state.update_data(file_id=message.document.file_id)
    await message.answer("🖼️ أرسل صورة الغلاف (اختياري)، أو أرسل كلمة 'تخطي':")
    await state.set_state(AdminFileStates.waiting_photo)


@router.message(AdminFileStates.waiting_photo)
async def file_photo(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else None

    repo = CodeFileRepository(session)
    item = await repo.create(
        title=data["title"], description=data["description"], category=data["category"],
        price=data["price"], file_id=data["file_id"], photo_id=photo_id,
    )
    await message.answer(f"✅ تم إضافة الملف {item.title} بنجاح.")
    await state.clear()


@router.callback_query(F.data.startswith("file_adm:"))
async def manage_file(callback: CallbackQuery, session) -> None:
    file_id = int(callback.data.split(":")[1])
    repo = CodeFileRepository(session)
    item = await repo.get(file_id)
    if not item:
        await callback.answer("⚠️ غير موجود.", show_alert=True)
        return

    text = (
        f"📦 <b>{item.title}</b>\n{item.description}\n"
        f"الفئة: {item.category} | السعر: {item.price}\nالتحميلات: {item.downloads}\n"
        f"الحالة: {'مفعّل' if item.is_active else 'متوقف'}"
    )
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"file_toggle:{file_id}")],
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"file_delete:{file_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:files")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("file_toggle:"))
async def toggle_file(callback: CallbackQuery, session) -> None:
    file_id = int(callback.data.split(":")[1])
    repo = CodeFileRepository(session)
    await repo.toggle(file_id)
    await callback.answer("✅ تم التحديث")
    await manage_file(callback, session)


@router.callback_query(F.data.startswith("file_delete:"))
async def delete_file(callback: CallbackQuery, session) -> None:
    file_id = int(callback.data.split(":")[1])
    repo = CodeFileRepository(session)
    await repo.update_fields(file_id, is_active=False)
    await callback.answer("🗑️ تم إخفاء الملف")
    await list_files(callback, session)
