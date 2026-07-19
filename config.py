import os

# ===== إعدادات أساسية (عدّلها أو ضعها كمتغيرات بيئة) =====

# توكن البوت اللي تاخذه من @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا")

# الآيدي الرقمي لحسابك في تليجرام (احصل عليه من بوت @userinfobot)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# سعر الشراء: كم يدفع الزبون مقابل كل نجمة واحدة (بعملتك المحلية)
BUY_PRICE_PER_STAR = float(os.getenv("BUY_PRICE_PER_STAR", "0.02"))

# سعر البيع: كم تدفع أنت للزبون مقابل كل نجمة يبيعها لك (لازم أقل من سعر الشراء عشان تربح)
SELL_PRICE_PER_STAR = float(os.getenv("SELL_PRICE_PER_STAR", "0.015"))

# اسم العملة اللي تظهر للزبون
CURRENCY = os.getenv("CURRENCY", "دولار")

# تفاصيل الحساب/المحفظة اللي يحول عليها الزبون فلوسه
BANK_DETAILS = os.getenv(
    "BANK_DETAILS",
    "اسم المحفظة: ...\nرقم الحساب: ...\nاسم صاحب الحساب: ..."
)

# اسم المستخدم بتاعك في تليجرام عشان الزبون يرسل لك النجوم كهدية عند البيع
ADMIN_TELEGRAM_USERNAME = os.getenv("ADMIN_TELEGRAM_USERNAME", "@your_username")

# مكان قاعدة البيانات
DB_PATH = os.getenv("DB_PATH", "stars_bot.db")

# أقل وأكثر كمية مسموحة في الطلب الواحد
MIN_QUANTITY = int(os.getenv("MIN_QUANTITY", "10"))
MAX_QUANTITY = int(os.getenv("MAX_QUANTITY", "10000"))
