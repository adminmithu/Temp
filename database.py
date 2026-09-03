import sqlite3
import hashlib
import time
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "sms_cache.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for seen SMS hashes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_sms (
        sms_hash TEXT PRIMARY KEY,
        phone_number TEXT,
        country TEXT,
        service TEXT,
        otp_code TEXT,
        seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table for enabled/disabled country settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS country_settings (
        country_name TEXT PRIMARY KEY,
        is_enabled INTEGER DEFAULT 1
    );
    """)

    # Table for individual number settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS number_settings (
        phone_number TEXT PRIMARY KEY,
        country_name TEXT,
        is_enabled INTEGER DEFAULT 1
    );
    """)

    # Table for stocked / discovered phone numbers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stocked_numbers (
        phone_number TEXT PRIMARY KEY,
        country_name TEXT,
        url TEXT,
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        announced INTEGER DEFAULT 0
    );
    """)

    # Table for user subscriptions with 5-minute expiry timer
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        phone_number TEXT,
        service_name TEXT,
        created_at INTEGER,
        expires_at INTEGER
    );
    """)

    conn.commit()
    conn.close()

def generate_sms_hash(phone_number: str, message_text: str, time_str: str) -> str:
    raw_str = f"{phone_number}:{message_text}:{time_str}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

def is_sms_seen(sms_hash: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_sms WHERE sms_hash = ?", (sms_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def mark_sms_seen(sms_hash: str, phone_number: str, country: str, service: str, otp_code: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO seen_sms (sms_hash, phone_number, country, service, otp_code)
    VALUES (?, ?, ?, ?, ?)
    """, (sms_hash, phone_number, country, service, otp_code))
    conn.commit()
    conn.close()

def is_country_enabled(country_name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_enabled FROM country_settings WHERE country_name = ?", (country_name,))
    row = cursor.fetchone()
    conn.close()
    if row is not None:
        return bool(row["is_enabled"])
    return True

def set_country_enabled(country_name: str, enabled: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO country_settings (country_name, is_enabled) VALUES (?, ?)
    ON CONFLICT(country_name) DO UPDATE SET is_enabled = excluded.is_enabled
    """, (country_name, 1 if enabled else 0))
    conn.commit()
    conn.close()

def is_number_enabled(phone_number: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_enabled FROM number_settings WHERE phone_number = ?", (phone_number,))
    row = cursor.fetchone()
    conn.close()
    if row is not None:
        return bool(row["is_enabled"])
    return True

def set_number_enabled(phone_number: str, enabled: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO number_settings (phone_number, is_enabled) VALUES (?, ?)
    ON CONFLICT(phone_number) DO UPDATE SET is_enabled = excluded.is_enabled
    """, (phone_number, 1 if enabled else 0))
    conn.commit()
    conn.close()

def add_stocked_number(phone_number: str, country_name: str, url: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO stocked_numbers (phone_number, country_name, url)
    VALUES (?, ?, ?)
    """, (phone_number, country_name, url))
    conn.commit()
    conn.close()

def get_stocked_numbers_by_country():
    """Get newly discovered stocked numbers grouped by country."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT country_name, COUNT(*) as count, GROUP_CONCAT(phone_number, ', ') as numbers
    FROM stocked_numbers
    GROUP BY country_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_stocked_announced(phone_number: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE stocked_numbers SET announced = 1 WHERE phone_number = ?", (phone_number,))
    conn.commit()
    conn.close()

def add_user_subscription(user_id: int, phone_number: str, service_name: str, duration_seconds: int = 300):
    """Add a 5-minute active subscription for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    now = int(time.time())
    expires_at = now + duration_seconds
    
    # Remove existing active subscription for same phone number
    cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND phone_number = ?", (user_id, phone_number))
    
    cursor.execute("""
    INSERT INTO user_subscriptions (user_id, phone_number, service_name, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, phone_number, service_name, now, expires_at))
    conn.commit()
    conn.close()

def remove_user_subscription(user_id: int, phone_number: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND phone_number = ?", (user_id, phone_number))
    conn.commit()
    conn.close()

def remove_all_user_subscriptions(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_subscriptions_for_number(phone_number: str):
    """Get active non-expired subscriptions for a phone number."""
    conn = get_connection()
    cursor = conn.cursor()
    now = int(time.time())
    cursor.execute("SELECT * FROM user_subscriptions WHERE phone_number = ? AND expires_at > ?", (phone_number, now))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_subscriptions_for_user(user_id: int):
    """Get all non-expired subscriptions for a specific user."""
    conn = get_connection()
    cursor = conn.cursor()
    now = int(time.time())
    cursor.execute("SELECT * FROM user_subscriptions WHERE user_id = ? AND expires_at > ? ORDER BY expires_at DESC", (user_id, now))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_countries_stats():
    """Get top active countries ranked by total SMS received."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT country, COUNT(*) as sms_count
    FROM seen_sms
    GROUP BY country
    ORDER BY sms_count DESC
    LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_sms_db(query: str, limit: int = 15):
    conn = get_connection()
    cursor = conn.cursor()
    search_pattern = f"%{query}%"
    cursor.execute("""
    SELECT * FROM seen_sms
    WHERE service LIKE ? OR phone_number LIKE ? OR country LIKE ? OR otp_code LIKE ?
    ORDER BY id DESC
    LIMIT ?
    """, (search_pattern, search_pattern, search_pattern, search_pattern, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_sms_for_number(phone_number: str, limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM seen_sms
    WHERE phone_number = ?
    ORDER BY id DESC
    LIMIT ?
    """, (phone_number, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
