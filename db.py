import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "data.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            credits INTEGER DEFAULT 0,
            created_at INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            details TEXT,
            active INTEGER DEFAULT 1
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS topup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            method_name TEXT,
            quantity INTEGER,
            total_price_display TEXT,
            proof_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS free_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            prompt TEXT,
            duration INTEGER,
            status TEXT DEFAULT 'pending',
            video_url TEXT,
            created_at INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        conn.commit()

        # قيم افتراضية للإعدادات لو مش موجودة
        defaults = {
            "welcome_text": "أهلاً بيك 👋\nأنا بوت توليد فيديوهات بالذكاء الاصطناعي.\nاختار من القائمة تحت:",
            "channel_button_text": "📢 قناة البوت",
            "channel_url": "https://t.me/",
            "force_sub_enabled": "0",
            "force_sub_channel": "",
            "force_sub_channel_url": "",
            "currency_label": "جنيه",
            "price_per_video": "10",
            "price_per_video_stars": "15",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        conn.commit()


# ---------------- الإعدادات ----------------
def get_setting(key, default=""):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings")
        return {r["key"]: r["value"] for r in c.fetchall()}


def get_price_per_video() -> float:
    try:
        return float(get_setting("price_per_video", "10") or 10)
    except ValueError:
        return 10.0


def get_price_per_video_stars() -> int:
    try:
        return int(float(get_setting("price_per_video_stars", "15") or 15))
    except ValueError:
        return 15


# ---------------- المستخدمين ----------------
def get_or_create_user(telegram_id, username):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = c.fetchone()
        if row:
            # نحدّث اليوزرنيم لو اتغير
            if username and row["username"] != username:
                c.execute("UPDATE users SET username=? WHERE telegram_id=?", (username, telegram_id))
            return dict(row)
        c.execute(
            "INSERT INTO users (telegram_id, username, created_at) VALUES (?,?,?)",
            (telegram_id, username, int(time.time())),
        )
        c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return dict(c.fetchone())


def get_user(telegram_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = c.fetchone()
        return dict(row) if row else None


def get_credits(telegram_id) -> int:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT credits FROM users WHERE telegram_id=?", (telegram_id,))
        row = c.fetchone()
        return row["credits"] if row else 0


def add_credits(telegram_id, amount):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET credits = credits + ? WHERE telegram_id=?",
            (amount, telegram_id),
        )


def decrement_credit(telegram_id) -> bool:
    """
    بينقص كريدت واحد لو فيه رصيد كافي، وبيرجع True لو نجح.
    الشرط 'credits > 0' جوه الاستعلام نفسه بيمنع الرصيد إنه ينزل تحت الصفر
    حتى لو حصل طلبين في نفس اللحظة بالظبط.
    """
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET credits = credits - 1 WHERE telegram_id=? AND credits > 0",
            (telegram_id,),
        )
        return c.rowcount > 0


def count_users():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM users")
        return c.fetchone()["cnt"]


def get_users_page(offset=0, limit=10):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in c.fetchall()]


def get_all_user_ids():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users")
        return [r["telegram_id"] for r in c.fetchall()]


# ---------------- المستخدمين المجانيين ----------------
def is_free_user(telegram_id) -> bool:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM free_users WHERE telegram_id=?", (telegram_id,))
        return c.fetchone() is not None


def add_free_user(telegram_id, username=""):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO free_users (telegram_id, username, added_at) VALUES (?,?,?)",
            (telegram_id, username, int(time.time())),
        )


def remove_free_user(telegram_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM free_users WHERE telegram_id=?", (telegram_id,))


def get_free_users():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM free_users ORDER BY added_at DESC")
        return [dict(r) for r in c.fetchall()]


# ---------------- طرق الدفع ----------------
def add_payment_method(name, details):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO payment_methods (name, details) VALUES (?, ?)", (name, details))


def toggle_payment_method(method_id, active):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE payment_methods SET active=? WHERE id=?", (active, method_id))


def delete_payment_method(method_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM payment_methods WHERE id=?", (method_id,))


def get_all_payment_methods():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM payment_methods ORDER BY id DESC")
        return [dict(r) for r in c.fetchall()]


def get_active_payment_methods():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM payment_methods WHERE active=1 ORDER BY id DESC")
        return [dict(r) for r in c.fetchall()]


# ---------------- طلبات شحن الرصيد (دفع يدوي) ----------------
def add_topup_request(telegram_id, username, method_name, quantity, total_price_display, proof_file_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO topup_requests "
            "(telegram_id, username, method_name, quantity, total_price_display, proof_file_id, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (telegram_id, username, method_name, quantity, total_price_display, proof_file_id, int(time.time())),
        )
        return c.lastrowid


def get_pending_topup_requests():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM topup_requests WHERE status='pending' ORDER BY created_at DESC")
        return [dict(r) for r in c.fetchall()]


def count_pending_topup_requests():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM topup_requests WHERE status='pending'")
        return c.fetchone()["cnt"]


def approve_topup_request(req_id):
    """
    بيوافق على طلب الشحن ويضيف الكريدت للمستخدم، بس لو الطلب لسه 'pending'
    (عشان منضيفش رصيد مرتين لو الأدمن ضغط قبول مرتين بالغلط).
    بيرجع (telegram_id, quantity) لو نجح، أو None لو الطلب مش موجود/اتعامل معاه قبل كده.
    """
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id, quantity, status FROM topup_requests WHERE id=?", (req_id,))
        row = c.fetchone()
        if not row or row["status"] != "pending":
            return None
        telegram_id = row["telegram_id"]
        quantity = row["quantity"]
        c.execute(
            "UPDATE users SET credits = credits + ? WHERE telegram_id=?",
            (quantity, telegram_id),
        )
        c.execute("UPDATE topup_requests SET status='approved' WHERE id=?", (req_id,))
        return telegram_id, quantity


def reject_topup_request(req_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id, status FROM topup_requests WHERE id=?", (req_id,))
        row = c.fetchone()
        if not row or row["status"] != "pending":
            return None
        c.execute("UPDATE topup_requests SET status='rejected' WHERE id=?", (req_id,))
        return row["telegram_id"]


# ---------------- توليد الفيديوهات ----------------
def add_generation(telegram_id, prompt, duration=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO generations (telegram_id, prompt, duration, created_at) VALUES (?,?,?,?)",
            (telegram_id, prompt, duration, int(time.time())),
        )
        return c.lastrowid


def update_generation(gen_id, status, video_url=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE generations SET status=?, video_url=? WHERE id=?",
            (status, video_url, gen_id),
        )
