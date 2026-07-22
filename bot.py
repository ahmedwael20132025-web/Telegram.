import asyncio
import logging
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    PreCheckoutQuery,
    LabeledPrice,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import config
import db
import admin_panel
from video_gen import generate_video
from image_gen import generate_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_panel.router)


# ---------------- الحالات (FSM) ----------------
class Generate(StatesGroup):
    waiting_prompt = State()
    waiting_style = State()
    waiting_duration = State()
    waiting_confirm = State()


class TopUp(StatesGroup):
    waiting_custom_quantity = State()
    waiting_proof = State()


QUANTITY_PRESETS = [5, 10, 20, 50]

# خيارات الستايل المتاحة لتوليد الفيديو والصور
STYLES = [
    ("📷 واقعي", "photorealistic, realistic style"),
    ("🎨 كرتون", "cartoon style, animated illustration"),
    ("🌸 أنمي", "anime style, japanese animation art"),
    ("🖌️ رسم فني", "artistic painting style, fine art"),
]


# ---------------- لوحات المفاتيح ----------------
def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    channel_text = db.get_setting("channel_button_text", "📢 قناة البوت")
    channel_url = db.get_setting("channel_url", "https://t.me/")
    rows = [
        [InlineKeyboardButton(text="🎬 إنشاء فيديو", callback_data="gen_video")],
        [InlineKeyboardButton(text="🖼 إنشاء صورة (مجاني)", callback_data="gen_image")],
        [InlineKeyboardButton(text="💰 شحن رصيد", callback_data="topup")],
        [InlineKeyboardButton(text="💵 الأسعار", callback_data="prices")],
        [InlineKeyboardButton(text="👤 حسابي", callback_data="my_account")],
    ]
    if channel_url and channel_url != "https://t.me/":
        rows.append([InlineKeyboardButton(text=channel_text, url=channel_url)])
    if admin_panel.is_admin(user_id):
        rows.append([InlineKeyboardButton(text="🛠 لوحة تحكم الأدمن", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]]
    )


def style_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, (label, _) in enumerate(STYLES):
        row.append(InlineKeyboardButton(text=label, callback_data=f"style_{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5 ثواني", callback_data="dur_5"),
                InlineKeyboardButton(text="10 ثواني", callback_data="dur_10"),
                InlineKeyboardButton(text="15 ثانية", callback_data="dur_15"),
            ],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")],
        ]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأكيد وإنشاء", callback_data="gen_confirm"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="gen_cancel"),
            ]
        ]
    )


def quantity_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for n in QUANTITY_PRESETS:
        row.append(InlineKeyboardButton(text=f"{n} فيديو", callback_data=f"topup_qty_{n}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔢 كمية تانية", callback_data="topup_custom")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_options_kb(quantity: int) -> InlineKeyboardMarkup:
    methods = db.get_active_payment_methods()
    rows = [
        [InlineKeyboardButton(text=f"💳 {m['name']}", callback_data=f"topup_method_{m['id']}_{quantity}")]
        for m in methods
    ]
    stars_price = db.get_price_per_video_stars() * quantity
    rows.append([InlineKeyboardButton(text=f"⭐ ادفع بـ {stars_price} نجمة (فوري)", callback_data=f"topup_stars_{quantity}")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="topup")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def check_join_kb() -> InlineKeyboardMarkup:
    url = db.get_setting("force_sub_channel_url", "")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 انضم للقناة", url=url)],
            [InlineKeyboardButton(text="✅ تحققت، كمّل", callback_data="check_join")],
        ]
    )


# ---------------- التحقق من الاشتراك الإجباري ----------------
async def is_force_sub_ok(user_id: int) -> bool:
    if db.get_setting("force_sub_enabled", "0") != "1":
        return True
    channel = db.get_setting("force_sub_channel", "")
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception as e:
        logger.warning(f"force sub check failed: {e}")
        return True


async def send_force_sub_message(message: Message):
    await message.answer(
        "⚠️ لازم تنضم لقناتنا الأول عشان تقدر تستخدم البوت:",
        reply_markup=check_join_kb(),
    )


# ---------------- /start ----------------
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.get_or_create_user(message.from_user.id, message.from_user.username or "")

    if not await is_force_sub_ok(message.from_user.id):
        await send_force_sub_message(message)
        return

    welcome = db.get_setting("welcome_text", "أهلاً بيك 👋")
    await message.answer(welcome, reply_markup=main_menu_kb(message.from_user.id))


@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery, state: FSMContext):
    if await is_force_sub_ok(callback.from_user.id):
        welcome = db.get_setting("welcome_text", "أهلاً بيك 👋")
        await callback.message.edit_text(welcome, reply_markup=main_menu_kb(callback.from_user.id))
    else:
        await callback.answer("لسه مش لاقيك في القناة 🤔", show_alert=True)


@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome = db.get_setting("welcome_text", "أهلاً بيك 👋")
    await callback.message.edit_text(welcome, reply_markup=main_menu_kb(callback.from_user.id))


# ---------------- حسابي ----------------
def has_free_access(telegram_id: int) -> bool:
    """الأدمن يستخدم البوت مجاني تلقائي، وكمان أي حد مضاف لقائمة المستخدمين المجانيين."""
    return admin_panel.is_admin(telegram_id) or db.is_free_user(telegram_id)


@dp.callback_query(F.data == "my_account")
async def my_account(callback: CallbackQuery):
    db.get_or_create_user(callback.from_user.id, callback.from_user.username or "")
    credits = db.get_credits(callback.from_user.id)
    is_admin_user = admin_panel.is_admin(callback.from_user.id)
    free = db.is_free_user(callback.from_user.id)
    lines = [
        "👤 حسابك:",
        "",
        f"💰 رصيدك الحالي: {credits} فيديو",
        "🖼 توليد الصور: مجاني دايماً، مش بيتخصم من رصيدك",
    ]
    if is_admin_user:
        lines.append("👑 أنت الأدمن، بتستخدم كل حاجة في البوت مجاناً بدون أي خصم.")
    elif free:
        lines.append("🆓 أنت من ضمن المستخدمين المميزين، بتستخدم الفيديو كمان مجاناً بدون خصم من رصيدك.")
    text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())


# ---------------- الأسعار (عرض للمستخدمين) ----------------
@dp.callback_query(F.data == "prices")
async def show_prices(callback: CallbackQuery):
    price = db.get_price_per_video()
    stars = db.get_price_per_video_stars()
    currency = db.get_setting("currency_label", "جنيه")
    text = (
        "💵 الأسعار\n\n"
        f"🎬 الفيديو: {price:g} {currency} أو {stars} نجمة ⭐ (لكل فيديو)\n"
        "🖼 الصور: 🎉 مجانية بالكامل، من غير حد أقصى\n"
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())


# ---------------- شحن الرصيد ----------------
@dp.callback_query(F.data == "topup")
async def topup_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    price = db.get_price_per_video()
    stars = db.get_price_per_video_stars()
    currency = db.get_setting("currency_label", "جنيه")
    text = (
        "💰 شحن الرصيد (لتوليد الفيديوهات)\n\n"
        f"سعر الفيديو الواحد: {price:g} {currency} أو {stars} نجمة تليجرام ⭐\n\n"
        "اختار كام فيديو عايز تشحن:"
    )
    await callback.message.edit_text(text, reply_markup=quantity_kb())


@dp.callback_query(F.data == "topup_custom")
async def topup_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopUp.waiting_custom_quantity)
    await callback.message.edit_text(
        "🔢 اكتب عدد الفيديوهات اللي عايز تشحنها (رقم بس):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="topup")]]
        ),
    )


@dp.message(TopUp.waiting_custom_quantity, F.text)
async def topup_custom_amount(message: Message, state: FSMContext):
    txt = message.text.strip()
    if not txt.isdigit() or int(txt) <= 0:
        await message.answer("⚠️ من فضلك ابعت رقم صحيح أكبر من صفر:")
        return
    quantity = int(txt)
    if quantity > 1000:
        await message.answer("⚠️ الحد الأقصى للشحن دفعة واحدة 1000 فيديو، اكتب رقم أصغر:")
        return
    await state.clear()
    await show_payment_options(message, quantity)


async def show_payment_options(target, quantity: int):
    price = db.get_price_per_video()
    currency = db.get_setting("currency_label", "جنيه")
    total = price * quantity
    methods = db.get_active_payment_methods()
    text = f"🧾 {quantity} فيديو = {total:g} {currency}\n\nاختار طريقة الدفع:"
    if not methods:
        text += "\n\n(مفيش طرق دفع يدوية متاحة حالياً، تقدر تدفع بالنجوم ⭐)"
    kb = payment_options_kb(quantity)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("topup_qty_"))
async def topup_qty_chosen(callback: CallbackQuery, state: FSMContext):
    quantity = int(callback.data.split("_")[-1])
    await show_payment_options(callback, quantity)


@dp.callback_query(F.data.startswith("topup_method_"))
async def topup_method_chosen(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    method_id = int(parts[2])
    quantity = int(parts[3])
    methods = {m["id"]: m for m in db.get_active_payment_methods()}
    method = methods.get(method_id)
    if not method:
        await callback.answer("الطريقة دي مش متاحة حالياً", show_alert=True)
        return

    price = db.get_price_per_video()
    currency = db.get_setting("currency_label", "جنيه")
    total = price * quantity
    total_display = f"{total:g} {currency}"

    await state.update_data(method_name=method["name"], quantity=quantity, total_display=total_display)
    await state.set_state(TopUp.waiting_proof)
    await callback.message.edit_text(
        f"💳 {method['name']}\n\n{method['details']}\n\n"
        f"المطلوب: {total_display} مقابل {quantity} فيديو\n\n"
        "بعد ما تحول، ابعت هنا صورة إيصال التحويل ✅"
    )


@dp.message(TopUp.waiting_proof, F.photo)
async def receive_topup_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    method_name = data.get("method_name", "غير محدد")
    quantity = data.get("quantity", 0)
    total_display = data.get("total_display", "")
    file_id = message.photo[-1].file_id

    req_id = db.add_topup_request(
        message.from_user.id,
        message.from_user.username or "",
        method_name,
        quantity,
        total_display,
        file_id,
    )
    await state.clear()
    await message.answer(
        "✅ تم استلام الإيصال، هيتم مراجعته والرد عليك قريب.",
        reply_markup=back_to_main_kb(),
    )

    if config.ADMIN_TELEGRAM_ID:
        try:
            await bot.send_photo(
                chat_id=config.ADMIN_TELEGRAM_ID,
                photo=file_id,
                caption=(
                    f"🔔 طلب شحن رصيد جديد\n"
                    f"المستخدم: @{message.from_user.username or message.from_user.id}\n"
                    f"الطريقة: {method_name}\n"
                    f"الكمية: {quantity} فيديو\n"
                    f"المبلغ: {total_display}"
                ),
                reply_markup=admin_panel.topup_review_kb(req_id),
            )
        except Exception as e:
            logger.warning(f"failed to notify admin: {e}")


@dp.message(TopUp.waiting_proof)
async def receive_topup_proof_invalid(message: Message):
    await message.answer("من فضلك ابعت صورة الإيصال 📸")


# ---------------- الدفع بنجوم تليجرام (Telegram Stars) ----------------
@dp.callback_query(F.data.startswith("topup_stars_"))
async def topup_stars(callback: CallbackQuery, state: FSMContext):
    quantity = int(callback.data.split("_")[-1])
    stars_amount = db.get_price_per_video_stars() * quantity
    if stars_amount <= 0:
        await callback.answer("سعر النجوم لسه متحددش، كلم الأدمن", show_alert=True)
        return

    payload = f"topup:{callback.from_user.id}:{quantity}:{int(time.time())}"
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"شحن {quantity} فيديو",
            description=f"شحن رصيد {quantity} فيديو في البوت",
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=f"{quantity} فيديو", amount=stars_amount)],
            provider_token="",
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"failed to send stars invoice: {e}")
        await callback.answer("حصل خطأ في إنشاء فاتورة الدفع، حاول تاني", show_alert=True)


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    try:
        _, telegram_id_str, quantity_str, _ = payload.split(":")
        telegram_id = int(telegram_id_str)
        quantity = int(quantity_str)
    except Exception as e:
        logger.error(f"bad payment payload '{payload}': {e}")
        return

    db.get_or_create_user(telegram_id, message.from_user.username or "")
    db.add_credits(telegram_id, quantity)
    new_balance = db.get_credits(telegram_id)
    stars_paid = message.successful_payment.total_amount

    await message.answer(
        f"✅ تم الدفع بنجاح! تم شحن {quantity} فيديو لرصيدك.\n"
        f"💰 رصيدك الحالي: {new_balance} فيديو",
        reply_markup=main_menu_kb(telegram_id),
    )

    if config.ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(
                config.ADMIN_TELEGRAM_ID,
                f"⭐ دفع نجوم تليجرام ناجح (تلقائي)\n"
                f"المستخدم: @{message.from_user.username or telegram_id}\n"
                f"الكمية: {quantity} فيديو\n"
                f"النجوم المدفوعة: {stars_paid}",
            )
        except Exception as e:
            logger.warning(f"failed to notify admin of stars payment: {e}")


# ---------------- توليد الفيديو / الصور ----------------
def user_can_generate_video(telegram_id: int) -> bool:
    return has_free_access(telegram_id) or db.get_credits(telegram_id) > 0


@dp.callback_query(F.data == "gen_video")
async def gen_video_start(callback: CallbackQuery, state: FSMContext):
    if not user_can_generate_video(callback.from_user.id):
        await callback.message.edit_text(
            "🚫 رصيدك خلص! اشحن رصيد جديد عشان تقدر تولّد فيديوهات.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💰 شحن رصيد", callback_data="topup")],
                    [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")],
                ]
            ),
        )
        return
    await state.update_data(kind="video")
    await state.set_state(Generate.waiting_prompt)
    await callback.message.edit_text(
        "🎬 وصف الفيديو\n\n"
        "اكتب وصف تفصيلي للفيديو اللي عايزه: مين/إيه اللي في المشهد، المكان، الحركة، الإضاءة والمزاج العام.\n"
        "كل ما الوصف يكون أدق، النتيجة بتبقى أحسن ✨",
        reply_markup=back_to_main_kb(),
    )


@dp.callback_query(F.data == "gen_image")
async def gen_image_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(kind="image")
    await state.set_state(Generate.waiting_prompt)
    await callback.message.edit_text(
        "🖼 وصف الصورة (مجاني بالكامل)\n\n"
        "اكتب وصف تفصيلي للصورة اللي عايزها: العناصر، الألوان، الجو العام، التفاصيل المهمة.\n"
        "كل ما الوصف يكون أدق، النتيجة بتبقى أحسن ✨",
        reply_markup=back_to_main_kb(),
    )


@dp.message(Generate.waiting_prompt, F.text)
async def gen_prompt_received(message: Message, state: FSMContext):
    await state.update_data(prompt=message.text)
    await state.set_state(Generate.waiting_style)
    await message.answer("🎨 اختار الستايل اللي عايزه:", reply_markup=style_kb())


@dp.callback_query(Generate.waiting_style, F.data.startswith("style_"))
async def gen_style_chosen(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[1])
    label, descriptor = STYLES[idx]
    await state.update_data(style_label=label, style_descriptor=descriptor)

    data = await state.get_data()
    if data.get("kind") == "video":
        await state.set_state(Generate.waiting_duration)
        await callback.message.edit_text("⏱ اختار مدة الفيديو:", reply_markup=duration_kb())
    else:
        await state.set_state(Generate.waiting_confirm)
        await show_confirm_screen(callback, state)


@dp.callback_query(Generate.waiting_duration, F.data.startswith("dur_"))
async def gen_duration_chosen(callback: CallbackQuery, state: FSMContext):
    duration = int(callback.data.split("_")[1])
    await state.update_data(duration=duration)
    await state.set_state(Generate.waiting_confirm)
    await show_confirm_screen(callback, state)


async def show_confirm_screen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind")
    prompt = data.get("prompt", "")
    style_label = data.get("style_label", "")

    if kind == "video":
        duration = data.get("duration", 5)
        free = has_free_access(callback.from_user.id)
        credits = db.get_credits(callback.from_user.id)
        cost_line = "🆓 مجاني (أدمن / مستخدم مميز)" if free else "1 فيديو من رصيدك"
        remaining_line = "" if free else f"الرصيد بعد الإنشاء: {max(credits - 1, 0)} فيديو"
        text = (
            "📋 مراجعة الطلب\n\n"
            f"📝 الوصف: {prompt}\n"
            f"🎨 الستايل: {style_label}\n"
            f"⏱ المدة: {duration} ثانية\n"
            f"💰 التكلفة: {cost_line}\n"
            f"{remaining_line}\n\n"
            "اتأكد من الوصف كويس، جاهز تبدأ؟"
        )
    else:
        text = (
            "📋 مراجعة الطلب\n\n"
            f"📝 الوصف: {prompt}\n"
            f"🎨 الستايل: {style_label}\n"
            "💰 التكلفة: 🆓 مجانية بالكامل\n\n"
            "اتأكد من الوصف كويس، جاهز تبدأ؟"
        )
    await callback.message.edit_text(text, reply_markup=confirm_kb())


@dp.callback_query(Generate.waiting_confirm, F.data == "gen_cancel")
async def gen_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome = db.get_setting("welcome_text", "أهلاً بيك 👋")
    await callback.message.edit_text(welcome, reply_markup=main_menu_kb(callback.from_user.id))


@dp.callback_query(Generate.waiting_confirm, F.data == "gen_confirm")
async def gen_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind")
    prompt = data.get("prompt", "")
    style_descriptor = data.get("style_descriptor", "")
    duration = data.get("duration", 5)
    await state.clear()

    telegram_id = callback.from_user.id
    final_prompt = f"{style_descriptor}, {prompt}" if style_descriptor else prompt

    if kind == "video":
        free = has_free_access(telegram_id)
        if not free and db.get_credits(telegram_id) <= 0:
            await callback.message.edit_text(
                "🚫 رصيدك خلص! اشحن رصيد جديد عشان تقدر تولّد فيديوهات.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💰 شحن رصيد", callback_data="topup")],
                        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")],
                    ]
                ),
            )
            return

        await callback.message.edit_text("⏳ جاري توليد الفيديو، ده ممكن ياخد دقيقة أو اتنين...")
        gen_id = db.add_generation(telegram_id, prompt, duration, kind="video")
        try:
            video_url = await asyncio.to_thread(generate_video, final_prompt, duration)
            db.update_generation(gen_id, "succeeded", video_url)
            if not free:
                db.decrement_credit(telegram_id)
            await callback.message.answer_video(
                video=video_url,
                caption="✅ اتفضل فيديوك جاهز!",
                reply_markup=main_menu_kb(telegram_id),
            )
        except Exception as e:
            logger.error(f"video generation failed: {e}")
            db.update_generation(gen_id, "failed")
            await callback.message.answer(
                "❌ حصل خطأ أثناء توليد الفيديو، ورصيدك متأثرش. حاول تاني كمان شوية.",
                reply_markup=main_menu_kb(telegram_id),
            )
    else:
        await callback.message.edit_text("⏳ جاري توليد الصورة...")
        gen_id = db.add_generation(telegram_id, prompt, None, kind="image")
        try:
            image_url = await asyncio.to_thread(generate_image, final_prompt)
            db.update_generation(gen_id, "succeeded", image_url)
            await callback.message.answer_photo(
                photo=image_url,
                caption="✅ اتفضل صورتك جاهزة!",
                reply_markup=main_menu_kb(telegram_id),
            )
        except Exception as e:
            logger.error(f"image generation failed: {e}")
            db.update_generation(gen_id, "failed")
            await callback.message.answer(
                "❌ حصل خطأ أثناء توليد الصورة، حاول تاني كمان شوية.",
                reply_markup=main_menu_kb(telegram_id),
            )


async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
