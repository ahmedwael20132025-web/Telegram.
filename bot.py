# -*- coding: utf-8 -*-
"""
بوت تليجرام لشراء وبيع نجوم تليجرام (Telegram Stars) مع هامش ربح.
يدير الطلبات، الدفع، والإحصائيات تلقائيًا — وأنت (الأدمن) تؤكد الدفع وترسل
النجوم يدويًا كهدية بعد التأكيد.
"""

import telebot
from telebot import types
import config
import database as db

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")
db.init_db()

# تخزين مؤقت لبيانات الطلب الجاري لكل مستخدم أثناء المحادثة
pending_flow = {}  # user_id -> dict


def is_admin(message):
    return message.from_user.id == config.ADMIN_ID


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("⭐ شراء نجوم", "💰 بيع نجوم")
    kb.row("📋 طلباتي")
    return kb


def cancel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("❌ إلغاء")
    return kb


# ================= بداية البوت =================

@bot.message_handler(commands=["start"])
def start(message):
    text = (
        "أهلاً بك 👋\n\n"
        "هذا البوت لشراء وبيع نجوم تليجرام (Telegram Stars).\n"
        f"سعر شراء النجمة الواحدة: <b>{db.get_buy_price()} {config.CURRENCY}</b>\n"
        f"سعر بيع النجمة الواحدة (لو تبيعلنا): <b>{db.get_sell_price()} {config.CURRENCY}</b>\n\n"
        "اختر من القائمة تحت 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "❌ إلغاء")
def cancel(message):
    pending_flow.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "تم الإلغاء.", reply_markup=main_menu())


# ================= تدفّق الشراء =================

@bot.message_handler(func=lambda m: m.text == "⭐ شراء نجوم")
def buy_start(message):
    pending_flow[message.from_user.id] = {"type": "buy"}
    bot.send_message(
        message.chat.id,
        f"كم عدد النجوم اللي تبي تشتريها؟\n"
        f"(الحد الأدنى {config.MIN_QUANTITY} - الحد الأقصى {config.MAX_QUANTITY})",
        reply_markup=cancel_kb(),
    )
    bot.register_next_step_handler(message, buy_quantity)


def buy_quantity(message):
    if message.text == "❌ إلغاء":
        return cancel(message)
    try:
        qty = int(message.text.strip())
        if not (config.MIN_QUANTITY <= qty <= config.MAX_QUANTITY):
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "الرجاء إدخال رقم صحيح ضمن الحدود المسموحة.")
        return bot.register_next_step_handler(message, buy_quantity)

    price = db.get_buy_price()
    total = round(qty * price, 2)
    order_id = db.create_order(
        message.from_user.id, message.from_user.username, "buy", qty, price
    )
    pending_flow[message.from_user.id] = {"type": "buy", "order_id": order_id}

    text = (
        f"🧾 طلبك رقم #{order_id}\n"
        f"الكمية: {qty} نجمة\n"
        f"الإجمالي: <b>{total} {config.CURRENCY}</b>\n\n"
        f"حوّل المبلغ إلى:\n{config.BANK_DETAILS}\n\n"
        "بعد التحويل، أرسل صورة إثبات الدفع (سكرين شوت) هنا 📸"
    )
    bot.send_message(message.chat.id, text, reply_markup=cancel_kb())
    bot.register_next_step_handler(message, buy_receive_proof)


def buy_receive_proof(message):
    if message.text == "❌ إلغاء":
        return cancel(message)
    flow = pending_flow.get(message.from_user.id)
    if not flow or "order_id" not in flow:
        return bot.send_message(message.chat.id, "ابدأ الطلب من جديد من القائمة الرئيسية.", reply_markup=main_menu())

    if not message.photo:
        bot.send_message(message.chat.id, "الرجاء إرسال صورة إثبات الدفع.")
        return bot.register_next_step_handler(message, buy_receive_proof)

    file_id = message.photo[-1].file_id
    order_id = flow["order_id"]
    db.attach_proof(order_id, file_id)
    order = db.get_order(order_id)

    bot.send_message(
        message.chat.id,
        f"✅ تم استلام إثبات الدفع لطلبك #{order_id}. بانتظار المراجعة والتأكيد.",
        reply_markup=main_menu(),
    )
    pending_flow.pop(message.from_user.id, None)
    notify_admin_new_order(order)


# ================= تدفّق البيع =================

@bot.message_handler(func=lambda m: m.text == "💰 بيع نجوم")
def sell_start(message):
    pending_flow[message.from_user.id] = {"type": "sell"}
    bot.send_message(
        message.chat.id,
        f"كم عدد النجوم اللي تبي تبيعها؟\n"
        f"(الحد الأدنى {config.MIN_QUANTITY} - الحد الأقصى {config.MAX_QUANTITY})",
        reply_markup=cancel_kb(),
    )
    bot.register_next_step_handler(message, sell_quantity)


def sell_quantity(message):
    if message.text == "❌ إلغاء":
        return cancel(message)
    try:
        qty = int(message.text.strip())
        if not (config.MIN_QUANTITY <= qty <= config.MAX_QUANTITY):
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "الرجاء إدخال رقم صحيح ضمن الحدود المسموحة.")
        return bot.register_next_step_handler(message, sell_quantity)

    price = db.get_sell_price()
    total = round(qty * price, 2)
    order_id = db.create_order(
        message.from_user.id, message.from_user.username, "sell", qty, price, status="pending_stars"
    )
    pending_flow[message.from_user.id] = {"type": "sell", "order_id": order_id}

    text = (
        f"🧾 طلب بيع رقم #{order_id}\n"
        f"الكمية: {qty} نجمة\n"
        f"سيصلك: <b>{total} {config.CURRENCY}</b>\n\n"
        f"أرسل النجوم الآن كهدية (Gift) إلى: {config.ADMIN_TELEGRAM_USERNAME}\n"
        "بعد الإرسال، اضغط الزر تحت 👇"
    )
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✅ أرسلت النجوم")
    kb.row("❌ إلغاء")
    bot.send_message(message.chat.id, text, reply_markup=kb)
    bot.register_next_step_handler(message, sell_confirm_sent)


def sell_confirm_sent(message):
    if message.text == "❌ إلغاء":
        return cancel(message)
    flow = pending_flow.get(message.from_user.id)
    if not flow or "order_id" not in flow or message.text != "✅ أرسلت النجوم":
        bot.send_message(message.chat.id, "اضغط الزر '✅ أرسلت النجوم' بعد إرسال النجوم فعليًا.")
        return bot.register_next_step_handler(message, sell_confirm_sent)

    order_id = flow["order_id"]
    db.update_order_status(order_id, "pending_review")
    order = db.get_order(order_id)

    bot.send_message(
        message.chat.id,
        f"✅ تم إشعارنا بطلب البيع #{order_id}. سنراجع استلام النجوم ونحول المبلغ لك بعد التأكيد.",
        reply_markup=main_menu(),
    )
    pending_flow.pop(message.from_user.id, None)
    notify_admin_new_order(order)


# ================= طلباتي =================

@bot.message_handler(func=lambda m: m.text == "📋 طلباتي")
def my_orders(message):
    orders = db.get_user_orders(message.from_user.id)
    if not orders:
        return bot.send_message(message.chat.id, "لا توجد طلبات سابقة.")
    status_ar = {
        "pending_proof": "بانتظار إثبات الدفع",
        "pending_stars": "بانتظار إرسال النجوم",
        "pending_review": "قيد المراجعة",
        "completed": "مكتمل ✅",
        "rejected": "مرفوض ❌",
    }
    lines = []
    for o in orders:
        kind = "شراء" if o["order_type"] == "buy" else "بيع"
        st = status_ar.get(o["status"], o["status"])
        lines.append(f"#{o['id']} — {kind} {o['quantity']} نجمة — {o['total_price']} {config.CURRENCY} — {st}")
    bot.send_message(message.chat.id, "\n".join(lines))


# ================= إشعارات الأدمن + الموافقة =================

def notify_admin_new_order(order):
    kind = "🟢 شراء" if order["order_type"] == "buy" else "🔵 بيع"
    text = (
        f"{kind} — طلب جديد #{order['id']}\n"
        f"العميل: @{order['username'] or order['user_id']}\n"
        f"الكمية: {order['quantity']} نجمة\n"
        f"المبلغ: {order['total_price']} {config.CURRENCY}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ تأكيد", callback_data=f"confirm:{order['id']}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject:{order['id']}"),
    )
    if order["order_type"] == "buy" and order["proof_file_id"]:
        bot.send_photo(config.ADMIN_ID, order["proof_file_id"], caption=text, reply_markup=kb)
    else:
        bot.send_message(config.ADMIN_ID, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith(("confirm:", "reject:")))
def handle_admin_decision(call):
    if call.from_user.id != config.ADMIN_ID:
        return bot.answer_callback_query(call.id, "هذا الإجراء للأدمن فقط.")

    action, order_id = call.data.split(":")
    order_id = int(order_id)
    order = db.get_order(order_id)
    if not order:
        return bot.answer_callback_query(call.id, "الطلب غير موجود.")

    if action == "reject":
        db.update_order_status(order_id, "rejected")
        bot.answer_callback_query(call.id, "تم رفض الطلب.")
        bot.send_message(order["user_id"], f"❌ تم رفض طلبك #{order_id}. تواصل معنا لمزيد من التفاصيل.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        return

    # تأكيد
    db.update_order_status(order_id, "completed")
    bot.answer_callback_query(call.id, "تم التأكيد ✅")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    if order["order_type"] == "buy":
        bot.send_message(
            order["user_id"],
            f"✅ تم تأكيد طلبك #{order_id}. جارِ إرسال {order['quantity']} نجمة لك كهدية الآن.",
        )
        bot.send_message(
            config.ADMIN_ID,
            f"🔔 تذكير: أرسل {order['quantity']} نجمة يدويًا إلى @{order['username'] or order['user_id']} الآن.",
        )
    else:
        bot.send_message(
            order["user_id"],
            f"✅ تم تأكيد استلام نجومك لطلب البيع #{order_id}. سيصلك {order['total_price']} {config.CURRENCY} قريبًا.",
        )
        bot.send_message(
            config.ADMIN_ID,
            f"🔔 تذكير: حوّل {order['total_price']} {config.CURRENCY} يدويًا لصاحب الطلب #{order_id}.",
        )


# ================= أوامر الأدمن =================

@bot.message_handler(commands=["setbuyprice"])
def set_buy_price(message):
    if not is_admin(message):
        return
    try:
        price = float(message.text.split(maxsplit=1)[1])
        db.set_setting("buy_price", price)
        bot.send_message(message.chat.id, f"تم تحديث سعر الشراء إلى {price} {config.CURRENCY}")
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "الاستخدام: /setbuyprice 0.02")


@bot.message_handler(commands=["setsellprice"])
def set_sell_price(message):
    if not is_admin(message):
        return
    try:
        price = float(message.text.split(maxsplit=1)[1])
        db.set_setting("sell_price", price)
        bot.send_message(message.chat.id, f"تم تحديث سعر البيع إلى {price} {config.CURRENCY}")
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "الاستخدام: /setsellprice 0.015")


@bot.message_handler(commands=["pending"])
def list_pending(message):
    if not is_admin(message):
        return
    orders = db.get_orders_by_status("pending_review")
    if not orders:
        return bot.send_message(message.chat.id, "لا توجد طلبات قيد المراجعة حاليًا.")
    for o in orders:
        notify_admin_new_order(o)


@bot.message_handler(commands=["stats"])
def stats(message):
    if not is_admin(message):
        return
    s = db.get_stats()
    profit_estimate = (
        s["buy_total"] - (s["buy_stars"] * 0)  # التكلفة الفعلية تعتمد على سعر شرائك من موردك
    )
    text = (
        "📊 <b>إحصائيات</b>\n\n"
        f"عمليات الشراء المكتملة: {s['buy_count']} ({s['buy_stars']} نجمة) — إجمالي: {s['buy_total']} {config.CURRENCY}\n"
        f"عمليات البيع المكتملة: {s['sell_count']} ({s['sell_stars']} نجمة) — إجمالي: {s['sell_total']} {config.CURRENCY}\n\n"
        "ملاحظة: الربح الحقيقي = ما استلمته من الزبائن ناقص تكلفة شرائك الفعلية للنجوم من موردك."
    )
    bot.send_message(message.chat.id, text)


if __name__ == "__main__":
    print("البوت يعمل الآن...")
    bot.infinity_polling()
