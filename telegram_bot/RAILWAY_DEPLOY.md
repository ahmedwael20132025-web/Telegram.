# نشر البوت على Railway

## الطريقة 1: عبر GitHub (الأسهل والموصى بها)

1. ارفع مجلد المشروع إلى مستودع GitHub جديد (خاص أو عام).
2. ادخل إلى [railway.app](https://railway.app) وسجّل الدخول.
3. اضغط **New Project** → **Deploy from GitHub repo** → اختر المستودع.
4. Railway سيكتشف تلقائيًا أنه مشروع Python (بفضل `requirements.txt` و`Procfile` و`railway.json` الموجودين).

## الطريقة 2: عبر Railway CLI (من جهازك مباشرة)

```bash
npm i -g @railway/cli
railway login
cd telegram_bot
railway init
railway up
```

## إعداد المتغيرات البيئية (مهم جدًا)

**لا تستخدم ملف `.env` على Railway.** بدلاً من ذلك:
1. من لوحة المشروع في Railway، افتح تبويب **Variables**.
2. أضف كل متغير من `.env.example` يدويًا:
   - `BOT_TOKEN` = توكن بوتك
   - `SUPER_ADMINS` = معرفك الرقمي
   - `CLAUDE_API_KEY` أو `OPENAI_API_KEY` (لتفعيل توليد الأكواد ومولّد المشاريع)
   - `DEFAULT_AI_PROVIDER` = claude أو openai

Railway يقرأ هذه المتغيرات كـ Environment Variables تلقائيًا؛ الكود مبني بحيث يقرأها بنفس الطريقة سواء من `.env` محليًا أو من Railway مباشرة.

## مشكلة تخزين قاعدة البيانات (مهم)

نظام ملفات Railway **مؤقت (ephemeral)** — أي نشر جديد (Redeploy) يمسح ملف `bot.db` وأي نسخ احتياطية محلية. لحل هذا لديك خياران:

**الخيار الأفضل: استخدام PostgreSQL (إضافة مجانية من Railway)**
1. من لوحة مشروعك: **New** → **Database** → **Add PostgreSQL**.
2. Railway سينشئ متغيرًا اسمه `DATABASE_URL` تلقائيًا بصيغة `postgresql://...` — يجب تعديله يدويًا في تبويب Variables ليصبح:
   ```
   postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME
   ```
   (فقط أضف `+asyncpg` بعد `postgresql`، لأن الكود يستخدم قيادة async).

**الخيار البديل: Volume دائم مع SQLite**
1. من إعدادات الخدمة: **Settings** → **Volumes** → أنشئ Volume واربطه بمسار مثل `/data`.
2. أضف متغير بيئة: `DATA_DIR=/data` (تُستخدم لحفظ النسخ الاحتياطية والملفات المولّدة).
3. عدّل `DATABASE_URL` إلى: `sqlite+aiosqlite:////data/bot.db`

## بعد النشر

- افتح تبويب **Deployments** لمتابعة السجلات (Logs) والتأكد من ظهور: `تم تشغيل البوت بنجاح.`
- إذا ظهر أي خطأ في السجلات، انسخه وأرسله لي كما هو لتشخيصه.
- البوت يعمل بنظام Polling (وليس Webhook)، لذلك لا تحتاج لأي إعداد دومين أو منفذ (Port) على Railway.
