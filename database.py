import aiosqlite
import os
from typing import Optional, List, Dict, Tuple
from config import DATABASE_NAME


class Database:
    def __init__(self):
        self.db_name = DATABASE_NAME

    async def create_tables(self):
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            await db.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance REAL DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                referred_by INTEGER,
                referral_code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_received INTEGER DEFAULT 0,
                total_sent INTEGER DEFAULT 0)""")

            await db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                message_type TEXT NOT NULL,
                message_content TEXT,
                receiver_message_id INTEGER,
                is_anonymous INTEGER DEFAULT 1,
                is_revealed INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revealed_at TIMESTAMP)""")

            await db.execute("""CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                bonus_paid INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

            await db.execute("""CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

            await db.execute("""CREATE TABLE IF NOT EXISTS premium_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                used_by INTEGER,
                is_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP)""")

            await db.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_recv ON messages(receiver_id, sent_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_send ON messages(sender_id, sent_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_recv_id ON messages(receiver_message_id)")

            await db.commit()

    # ===== ПОЛЬЗОВАТЕЛИ =====
    async def register_user(self, user_id, username=None, first_name=None, last_name=None, referred_by=None):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
            existing = await cursor.fetchone()

            if existing:
                await db.execute("""UPDATE users SET username=?, first_name=?, last_name=?,
                    last_active=CURRENT_TIMESTAMP WHERE user_id=?""",
                    (username, first_name, last_name, user_id))
                await db.commit()
                return False
            else:
                referral_code = f"REF{user_id}{os.urandom(2).hex()}"
                await db.execute("""INSERT INTO users 
                    (user_id, username, first_name, last_name, referred_by, referral_code)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, username, first_name, last_name, referred_by, referral_code))
                await db.commit()
                return True

    async def get_user(self, user_id) -> Optional[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return await cursor.fetchone()

    # ===== БАЛАНС =====
    async def get_balance(self, user_id) -> float:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            r = await cursor.fetchone()
            return r[0] if r else 0

    async def add_balance(self, user_id, amount, description=""):
        if amount == 0:
            return False
        async with aiosqlite.connect(self.db_name) as db:
            if amount < 0:
                cursor = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
                r = await cursor.fetchone()
                if not r or r[0] + amount < 0:
                    return False
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
            await db.execute("""INSERT INTO transactions (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)""",
                (user_id, amount, "credit" if amount > 0 else "debit", description))
            await db.commit()
            return True

    async def get_transactions(self, user_id, limit=20) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT * FROM transactions WHERE user_id=?
                ORDER BY created_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    # ===== PREMIUM =====
    async def is_premium(self, user_id) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,))
            r = await cursor.fetchone()
            return bool(r[0]) if r else False

    async def set_premium(self, user_id, status=True):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_premium=? WHERE user_id=?",
                (1 if status else 0, user_id))
            await db.commit()

    async def buy_premium(self, user_id) -> Tuple[bool, str]:
        from config import PREMIUM_PRICE
        if await self.is_premium(user_id):
            return False, "У вас уже есть Premium!"
        balance = await self.get_balance(user_id)
        if balance < PREMIUM_PRICE:
            return False, f"Недостаточно монет. Нужно {PREMIUM_PRICE}, у вас {balance}"
        if await self.add_balance(user_id, -PREMIUM_PRICE, "Покупка Premium"):
            await self.set_premium(user_id, True)
            return True, "Premium активирован!"
        return False, "Ошибка покупки"

    # ===== БАН =====
    async def ban_user(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
            await db.commit()

    async def unban_user(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
            await db.commit()

    async def is_banned(self, user_id) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
            r = await cursor.fetchone()
            return bool(r[0]) if r else False

    # ===== СООБЩЕНИЯ =====
    async def save_message(self, sender_id, receiver_id, message_type,
                          content="", receiver_message_id=None) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""INSERT INTO messages
                (sender_id, receiver_id, message_type, message_content, receiver_message_id)
                VALUES (?, ?, ?, ?, ?)""",
                (sender_id, receiver_id, message_type, content, receiver_message_id))
            await db.execute("UPDATE users SET total_sent=total_sent+1 WHERE user_id=?", (sender_id,))
            await db.execute("UPDATE users SET total_received=total_received+1 WHERE user_id=?", (receiver_id,))
            await db.commit()
            return cursor.lastrowid

    async def get_message_by_receiver_id(self, receiver_message_id) -> Optional[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT * FROM messages
                WHERE receiver_message_id=? AND is_deleted=0
                ORDER BY id DESC LIMIT 1""", (receiver_message_id,))
            return await cursor.fetchone()

    async def get_message_by_id(self, message_id) -> Optional[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM messages WHERE id=? AND is_deleted=0", (message_id,))
            return await cursor.fetchone()

    async def reveal_message(self, message_id) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""UPDATE messages SET is_revealed=1, revealed_at=CURRENT_TIMESTAMP
                WHERE id=?""", (message_id,))
            await db.commit()
            return True

    async def delete_message(self, message_id) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE messages SET is_deleted=1 WHERE id=?", (message_id,))
            await db.commit()
            return True

    async def toggle_favorite(self, message_id) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_favorite FROM messages WHERE id=?", (message_id,))
            r = await cursor.fetchone()
            if r:
                new = 0 if r[0] else 1
                await db.execute("UPDATE messages SET is_favorite=? WHERE id=?", (new, message_id))
                await db.commit()
                return bool(new)
            return False

    async def get_received_messages(self, user_id, limit=20) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT m.*, u.username, u.first_name
                FROM messages m LEFT JOIN users u ON m.sender_id=u.user_id
                WHERE m.receiver_id=? AND m.is_deleted=0
                ORDER BY m.sent_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    async def get_sent_messages(self, user_id, limit=20) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT m.*, u.username, u.first_name
                FROM messages m LEFT JOIN users u ON m.receiver_id=u.user_id
                WHERE m.sender_id=? AND m.is_deleted=0
                ORDER BY m.sent_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    async def get_favorite_messages(self, user_id, limit=20) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT m.*, u.username, u.first_name
                FROM messages m LEFT JOIN users u ON m.sender_id=u.user_id
                WHERE m.receiver_id=? AND m.is_favorite=1 AND m.is_deleted=0
                ORDER BY m.sent_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    # ===== РЕФЕРАЛЫ =====
    async def add_referral(self, referrer_id, referred_id) -> Tuple[bool, str]:
        from config import REFERRAL_BONUS
        if referrer_id == referred_id:
            return False, "Нельзя пригласить себя"
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT id FROM referrals WHERE referred_id=?", (referred_id,))
            if await cursor.fetchone():
                return False, "Вы уже чей-то реферал"
            await db.execute("""INSERT INTO referrals (referrer_id, referred_id, bonus_paid)
                VALUES (?, ?, 1)""", (referrer_id, referred_id))
            await db.commit()
            await self.add_balance(referrer_id, REFERRAL_BONUS, f"Реферал {referred_id}")
            return True, f"+{REFERRAL_BONUS} монет"

    async def get_referral_count(self, user_id) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
            r = await cursor.fetchone()
            return r[0] if r else 0

    async def get_referrals(self, user_id, limit=50) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT r.*, u.username, u.first_name, u.created_at
                FROM referrals r LEFT JOIN users u ON r.referred_id=u.user_id
                WHERE r.referrer_id=? ORDER BY r.created_at DESC LIMIT ?""", (user_id, limit))
            return await cursor.fetchall()

    # ===== ПРОМОКОДЫ =====
    async def create_premium_code(self, admin_id, code) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            try:
                await db.execute("INSERT INTO premium_codes (code, created_by) VALUES (?, ?)",
                    (code, admin_id))
                await db.commit()
                return True
            except:
                return False

    async def use_premium_code(self, user_id, code) -> Tuple[bool, str]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM premium_codes WHERE code=? AND is_used=0", (code,))
            r = await cursor.fetchone()
            if not r:
                return False, "Промокод не найден или использован"
            if await self.is_premium(user_id):
                return False, "У вас уже есть Premium"
            await db.execute("""UPDATE premium_codes SET used_by=?, is_used=1, used_at=CURRENT_TIMESTAMP
                WHERE code=?""", (user_id, code))
            await db.execute("UPDATE users SET is_premium=1 WHERE user_id=?", (user_id,))
            await db.commit()
            return True, "Premium активирован!"

    # ===== СТАТИСТИКА =====
    async def get_full_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_name) as db:
            s = {}
            for key, q in [
                ('total_users', "SELECT COUNT(*) FROM users"),
                ('banned_users', "SELECT COUNT(*) FROM users WHERE is_banned=1"),
                ('premium_users', "SELECT COUNT(*) FROM users WHERE is_premium=1"),
                ('today_users', "SELECT COUNT(*) FROM users WHERE created_at > datetime('now','-1 day')"),
                ('total_messages', "SELECT COUNT(*) FROM messages WHERE is_deleted=0"),
                ('revealed_messages', "SELECT COUNT(*) FROM messages WHERE is_revealed=1 AND is_deleted=0"),
                ('today_messages', "SELECT COUNT(*) FROM messages WHERE sent_at > datetime('now','-1 day') AND is_deleted=0"),
                ('total_referrals', "SELECT COUNT(*) FROM referrals"),
                ('used_codes', "SELECT COUNT(*) FROM premium_codes WHERE is_used=1"),
            ]:
                cursor = await db.execute(q)
                s[key] = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT SUM(balance) FROM users")
            s['total_balance'] = (await cursor.fetchone())[0] or 0
            return s

    async def get_top_receivers(self, limit=10) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT u.user_id, u.username, u.first_name, u.total_received
                FROM users u WHERE u.is_banned=0
                ORDER BY u.total_received DESC LIMIT ?""", (limit,))
            return await cursor.fetchall()

    async def get_top_referrers(self, limit=10) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT u.user_id, u.username, u.first_name,
                COUNT(r.id) as ref_count FROM users u
                LEFT JOIN referrals r ON u.user_id=r.referrer_id
                WHERE u.is_banned=0 GROUP BY u.user_id
                ORDER BY ref_count DESC LIMIT ?""", (limit,))
            return await cursor.fetchall()

    async def search_users(self, query, limit=10) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            if query.isdigit():
                cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (int(query),))
                return await cursor.fetchall()
            q = query.lstrip("@")
            cursor = await db.execute("""SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?
                OR last_name LIKE ? LIMIT ?""", (f"%{q}%", f"%{q}%", f"%{q}%", limit))
            return await cursor.fetchall()

    # ===== ЛОГИ =====
    async def add_log(self, admin_id, action, target_id=None, details=None):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""INSERT INTO admin_logs (admin_id, action, target_id, details)
                VALUES (?, ?, ?, ?)""", (admin_id, action, target_id, details))
            await db.commit()

    async def get_logs(self, limit=50) -> List[Tuple]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT l.*, u.username FROM admin_logs l
                LEFT JOIN users u ON l.admin_id=u.user_id
                ORDER BY l.created_at DESC LIMIT ?""", (limit,))
            return await cursor.fetchall()

    async def get_all_active_users(self) -> List[int]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""SELECT user_id FROM users WHERE is_banned=0
                AND last_active > datetime('now','-30 days')""")
            return [r[0] for r in await cursor.fetchall()]
