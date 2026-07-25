"""
لوحة الأدمن: إدارة قنوات الاشتراك الإجباري
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repository import ChannelRepository
from filters.admin_filter import IsAdmin
from states.admin_states import AdminChannelStates
from utils.helpers import is_valid_channel_id

router = Router(name="admin_channels")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:channels")
async def list_channels(callback: CallbackQuery, session) -> None:
    repo = ChannelRepository(session)
    channels = await repo.list_all()

    rows = [
        [InlineKeyboardButton(
            text=f"{'✅' if c.is_active else '🚫'} {c.title}", callback_data=f"chan_adm:{c.id}"
        )]
        for c in channels
    ]
    rows.append([InlineKeyboardButton(text="➕ إضافة قناة", callback_data="chan_new")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:main")])

    await callback.message.edit_text("📢 قنوات الاشتراك الإجباري", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "chan_new")
async def create_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "✍️ أرسل معرّف القناة (Chat ID مثل -1001234567890 أو @channel_username):"
    )
    await state.set_state(AdminChannelStates.waiting_chat_id)
    await callback.answer()


@router.message(AdminChannelStates.waiting_chat_id)
async def create_channel_id(message: Message, state: FSMContext) -> None:
    chat_id = message.text.strip()
    if not is_valid_channel_id(chat_id):
        await message.answer("⚠️ صيغة غير صحيحة. أرسل مثل -1001234567890 أو @channel_username")
        return
    await state.update_data(chat_id=chat_id)
    await message.answer("✍️ أرسل اسم القناة المعروض للمستخدمين:")
    await state.set_state(AdminChannelStates.waiting_title)


@router.message(AdminChannelStates.waiting_title)
async def create_channel_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await message.answer("🔗 أرسل رابط دعوة القناة (https://t.me/...):")
    await state.set_state(AdminChannelStates.waiting_link)


@router.message(AdminChannelStates.waiting_link)
async def create_channel_link(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    repo = ChannelRepository(session)
    channel = await repo.create(data["chat_id"], data["title"], message.text.strip())
    await message.answer(f"✅ تم إضافة قناة {channel.title} بنجاح.")
    await state.clear()


@router.callback_query(F.data.startswith("chan_adm:"))
async def manage_channel(callback: CallbackQuery, session) -> None:
    channel_id = int(callback.data.split(":")[1])
    repo = ChannelRepository(session)
    channel = await repo.get(channel_id)
    if not channel:
        await callback.answer("⚠️ القناة غير موجودة.", show_alert=True)
        return

    text = f"📢 <b>{channel.title}</b>\n{channel.invite_link}\nالحالة: {'مفعّلة' if channel.is_active else 'متوقفة'}"
    rows = [
        [InlineKeyboardButton(text="🔁 تفعيل/تعطيل", callback_data=f"chan_toggle:{channel_id}")],
        [InlineKeyboardButton(text="⬆️ لأعلى", callback_data=f"chan_up:{channel_id}"),
         InlineKeyboardButton(text="⬇️ لأسفل", callback_data=f"chan_down:{channel_id}")],
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"chan_delete:{channel_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:channels")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("chan_toggle:"))
async def toggle_channel(callback: CallbackQuery, session) -> None:
    channel_id = int(callback.data.split(":")[1])
    repo = ChannelRepository(session)
    channel = await repo.get(channel_id)
    if channel:
        await repo.update_fields(channel_id, is_active=not channel.is_active)
    await callback.answer("✅ تم التحديث")
    await manage_channel(callback, session)


@router.callback_query(F.data.startswith("chan_delete:"))
async def delete_channel(callback: CallbackQuery, session) -> None:
    channel_id = int(callback.data.split(":")[1])
    repo = ChannelRepository(session)
    await repo.delete(channel_id)
    await callback.answer("🗑️ تم الحذف")
    await list_channels(callback, session)


@router.callback_query(F.data.startswith("chan_up:"))
async def move_channel_up(callback: CallbackQuery, session) -> None:
    await _reorder(callback, session, -1)


@router.callback_query(F.data.startswith("chan_down:"))
async def move_channel_down(callback: CallbackQuery, session) -> None:
    await _reorder(callback, session, 1)


async def _reorder(callback: CallbackQuery, session, direction: int) -> None:
    channel_id = int(callback.data.split(":")[1])
    repo = ChannelRepository(session)
    channels = await repo.list_all()
    ids = [c.id for c in channels]
    if channel_id not in ids:
        await callback.answer()
        return
    index = ids.index(channel_id)
    new_index = index + direction
    if 0 <= new_index < len(ids):
        ids[index], ids[new_index] = ids[new_index], ids[index]
        for order, cid in enumerate(ids):
            await repo.update_fields(cid, sort_order=order)
    await callback.answer("✅ تم إعادة الترتيب")
    await manage_channel(callback, session)
