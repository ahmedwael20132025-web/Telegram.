import sqlite3
from datetime import datetime
import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            order_type TEXT NOT NULL,        -- 'buy' أو 'sell'
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_proof',
            proof_file_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def get_buy_price():
    return float(get_setting("buy_price", config.BUY_PRICE_PER_STAR))


def get_sell_price():
    return float(get_setting("sell_price", config.SELL_PRICE_PER_STAR))


def create_order(user_id, username, order_type, quantity, unit_price, status="pending_proof"):
    total = round(quantity * unit_price, 4)
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO orders (user_id, username, order_type, quantity, unit_price, total_price, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, order_type, quantity, unit_price, total, status, datetime.now().isoformat()),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return order_id


def attach_proof(order_id, file_id):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET proof_file_id=?, status='pending_review', updated_at=? WHERE id=?",
        (file_id, datetime.now().isoformat(), order_id),
    )
    conn.commit()
    conn.close()


def update_order_status(order_id, status):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status=?, updated_at=? WHERE id=?",
        (status, datetime.now().isoformat(), order_id),
    )
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return row


def get_orders_by_status(status):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE status=? ORDER BY id DESC", (status,)
    ).fetchall()
    conn.close()
    return rows


def get_user_orders(user_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_stats():
    conn = get_conn()
    buy = conn.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(total_price),0) s, COALESCE(SUM(quantity),0) q "
        "FROM orders WHERE order_type='buy' AND status='completed'"
    ).fetchone()
    sell = conn.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(total_price),0) s, COALESCE(SUM(quantity),0) q "
        "FROM orders WHERE order_type='sell' AND status='completed'"
    ).fetchone()
    conn.close()
    return {
        "buy_count": buy["c"], "buy_total": buy["s"], "buy_stars": buy["q"],
        "sell_count": sell["c"], "sell_total": sell["s"], "sell_stars": sell["q"],
    }
