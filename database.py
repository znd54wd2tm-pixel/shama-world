import sqlite3
from datetime import date

DB_NAME = "case_world.db"

def connect():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 1000,
            cases_opened INTEGER DEFAULT 0,
            last_bonus TEXT,
            registered_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def create_user(telegram_id, username, first_name):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT telegram_id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users
            (telegram_id, username, first_name, balance, registered_at)
            VALUES (?, ?, ?, 1000, ?)
        """, (telegram_id, username, first_name, date.today().isoformat()))
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT telegram_id, username, first_name,
               balance, cases_opened, last_bonus, registered_at
        FROM users WHERE telegram_id = ?
    """, (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_balance(telegram_id, amount):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
        (amount, telegram_id)
    )
    conn.commit()
    conn.close()

def update_bonus_date(telegram_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET last_bonus = ? WHERE telegram_id = ?",
        (date.today().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()
