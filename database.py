import aiosqlite
from typing import Optional, List, Dict, Tuple
from config import DATABASE_NAME

class Database:
    def __init__(self):
        self.db_name = DATABASE_NAME

    async def create_tables(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                last_name TEXT, balance REAL DEFAULT 0, is_premium INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0, referred_by INTEGER,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER,
                receiver_id INTEGER, receiver_message_id INTEGER,
                message_type TEXT, content TEXT, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_revealed INTEGER DEFAULT 0, is_deleted INTEGER DEFAULT 0)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER,
                referred_id INTEGER, bonus_paid INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER,
                action TEXT, target_id INTEGER, details TEXT,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS premium_codes (
                code TEXT PRIMARY KEY, created_by INTEGER, used_by INTEGER,
                is_used INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            
            await db.commit()

    # === ПОЛЬЗОВАТЕЛИ ===
    async def register_user(self, user_id, username=None, first_name=None, last_name=None, referred_by=None):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, referred_by)
                VALUES (?, ?, ?, ?, COALESCE((SELECT referred_by FROM users WHERE user_id=?), ?))""",
                (user_id, username, first_name, last_name, referred_by, referred_by))
            await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return await cursor.fetchone()

    async def add_balance(self, user_id, amount):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
            await db.commit()

    async def get_balance(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def set_premium(self, user_id, status=1):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_premium=? WHERE user_id=?", (status, user_id))
            await db.commit()

    async def is_premium(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,))
            result = await cursor.fetchone()
            return bool(result[0]) if result else False

    async def ban_user(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
            await db.commit()

    async def unban_user(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
            await db.commit()

    async def is_banned(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
            result = await cursor.fetchone()
            return bool(result[0]) if result else False

    # === СООБЩЕНИЯ ===
    async def save_message(self, sender_id, receiver_id, receiver_message_id, message_type, content=""):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""INSERT INTO messages (sender_id, receiver_id, receiver_message_id, message_type, content)
                VALUES (?, ?, ?, ?, ?)""", (sender_id, receiver_id, receiver_message_id, message_type, content))
            await db.commit()
            return cursor.lastrowid

    async def get_sender(self, receiver_message_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT sender_id FROM messages WHERE receiver_message_id=? AND is_deleted=0",
                (receiver_message_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def mark_revealed(self, receiver_message_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE messages SET is_revealed=1 WHERE receiver_message_id=?", (receiver_message_id,))
            await db.commit()

    async def is_revealed(self, receiver_message_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_revealed FROM messages WHERE receiver_message_id=?", (receiver_message_id,))
            result = await cursor.fetchone()
            return bool(result[0]) if result else False

    async def get_user_messages(self, user_id, limit=20):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT m.*, u.username, u.first_name FROM messages m
                JOIN users u ON m.sender_id=u.user_id
                WHERE m.receiver_id=? AND m.is_deleted=0
                ORDER BY m.sent_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    async def get_sent_messages(self, user_id, limit=20):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT m.*, u.username, u.first_name FROM messages m
                JOIN users u ON m.receiver_id=u.user_id
                WHERE m.sender_id=? AND m.is_deleted=0
                ORDER BY m.sent_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    # === РЕФЕРАЛЫ ===
    async def add_referral(self, referrer_id, referred_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referrer_id, referred_id))
            await db.commit()

    async def get_referral_count(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_referrals(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT r.*, u.username, u.first_name FROM referrals r
                JOIN users u ON r.referred_id=u.user_id WHERE r.referrer_id=?""", (user_id,))
            return await cursor.fetchall()

    # === ПРЕМИУМ КОДЫ ===
    async def create_premium_code(self, code, admin_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO premium_codes (code, created_by) VALUES (?, ?)", (code, admin_id))
            await db.commit()

    async def use_premium_code(self, code, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM premium_codes WHERE code=? AND is_used=0", (code,))
            result = await cursor.fetchone()
            if result:
                await db.execute("UPDATE premium_codes SET used_by=?, is_used=1 WHERE code=?", (user_id, code))
                await self.set_premium(user_id, 1)
                await db.commit()
                return True
            return False

    # === СТАТИСТИКА ===
    async def get_stats(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
            premium_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_deleted=0")
            total_messages = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_revealed=1 AND is_deleted=0")
            revealed = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM referrals")
            total_referrals = (await cursor.fetchone())[0]
            
            return {
                "total_users": total_users,
                "premium_users": premium_users,
                "total_messages": total_messages,
                "revealed_messages": revealed,
                "total_referrals": total_referrals
            }

    async def get_top_users(self, limit=10):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT u.user_id, u.username, u.first_name, COUNT(m.id) as msg_count
                FROM users u LEFT JOIN messages m ON u.user_id=m.receiver_id AND m.is_deleted=0
                GROUP BY u.user_id ORDER BY msg_count DESC LIMIT ?""", (limit,))
            return await cursor.fetchall()

    async def search_users(self, query):
        async with aiosqlite.connect(self.db_name) as db:
            if query.isdigit():
                cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (int(query),))
                return await cursor.fetchall()
            cursor = await db.execute("SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?",
                (f"%{query}%", f"%{query}%"))
            return await cursor.fetchall()

    # === ЛОГИ ===
    async def add_log(self, admin_id, action, target_id=None, details=None):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
                (admin_id, action, target_id, details))
            await db.commit()

    async def get_logs(self, limit=50):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT l.*, u.username FROM admin_logs l
                LEFT JOIN users u ON l.admin_id=u.user_id ORDER BY l.performed_at DESC LIMIT ?""", (limit,))
            return await cursor.fetchall()
