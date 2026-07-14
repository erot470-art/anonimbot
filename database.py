cat > database.py << 'EOF'
import aiosqlite
import os
from typing import Optional, Tuple, List, Dict
from config import DATABASE_NAME


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name

    async def create_tables(self):
        """Создание таблиц"""
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    receiver_message_id INTEGER,
                    message_type TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_revealed INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id INTEGER PRIMARY KEY,
                    amount REAL DEFAULT 0
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_id INTEGER,
                    details TEXT,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()

    async def register_user(self, user_id: int, username: str = None, 
                           first_name: str = None, last_name: str = None):
        """Регистрация пользователя"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name
            """, (user_id, username, first_name, last_name))
            await db.commit()

    async def save_message(self, sender_id: int, receiver_id: int, 
                          receiver_message_id: int, message_type: str) -> int:
        """Сохранение сообщения"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                INSERT INTO messages (sender_id, receiver_id, receiver_message_id, message_type)
                VALUES (?, ?, ?, ?)
            """, (sender_id, receiver_id, receiver_message_id, message_type))
            await db.commit()
            return cursor.lastrowid

    async def get_sender_id(self, receiver_message_id: int) -> Optional[int]:
        """Получить ID отправителя"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT sender_id FROM messages 
                WHERE receiver_message_id = ? AND is_deleted = 0
            """, (receiver_message_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def get_user_info(self, user_id: int) -> Optional[Tuple]:
        """Получить информацию о пользователе"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT username, first_name, last_name 
                FROM users WHERE user_id = ?
            """, (user_id,))
            return await cursor.fetchone()

    async def mark_as_revealed(self, receiver_message_id: int):
        """Отметить как раскрытое"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                UPDATE messages SET is_revealed = 1 
                WHERE receiver_message_id = ?
            """, (receiver_message_id,))
            await db.commit()

    async def is_already_revealed(self, receiver_message_id: int) -> bool:
        """Проверить, раскрыто ли уже"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT is_revealed FROM messages 
                WHERE receiver_message_id = ?
            """, (receiver_message_id,))
            result = await cursor.fetchone()
            return bool(result[0]) if result else False

    async def get_total_stats(self) -> Dict:
        """Статистика"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_deleted = 0")
            total_messages = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_revealed = 1 AND is_deleted = 0")
            revealed_messages = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE date(sent_at) = date('now') AND is_deleted = 0")
            today_messages = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(registered_at) = date('now')")
            today_users = (await cursor.fetchone())[0]
            
            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "revealed_messages": revealed_messages,
                "today_messages": today_messages,
                "today_users": today_users
            }
    
    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Топ пользователей"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT u.user_id, u.username, u.first_name, COUNT(m.id) as msg_count
                FROM users u
                LEFT JOIN messages m ON u.user_id = m.receiver_id AND m.is_deleted = 0
                WHERE u.is_banned = 0
                GROUP BY u.user_id
                ORDER BY msg_count DESC
                LIMIT ?
            """, (limit,))
            
            results = await cursor.fetchall()
            return [{"user_id": r[0], "username": r[1], "first_name": r[2], "msg_count": r[3]} for r in results]
    
    async def search_user(self, query: str) -> List[Dict]:
        """Поиск пользователя"""
        async with aiosqlite.connect(self.db_name) as db:
            if query.isdigit():
                cursor = await db.execute("""
                    SELECT user_id, username, first_name, last_name, registered_at, is_banned
                    FROM users WHERE user_id = ?
                """, (int(query),))
                result = await cursor.fetchone()
                if result:
                    return [{"user_id": result[0], "username": result[1], "first_name": result[2], 
                            "last_name": result[3], "registered_at": result[4], "is_banned": result[5]}]
            
            cursor = await db.execute("""
                SELECT user_id, username, first_name, last_name, registered_at, is_banned
                FROM users WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                LIMIT 10
            """, (f"%{query}%", f"%{query}%", f"%{query}%"))
            
            results = await cursor.fetchall()
            return [{"user_id": r[0], "username": r[1], "first_name": r[2], 
                    "last_name": r[3], "registered_at": r[4], "is_banned": r[5]} for r in results]
    
    async def ban_user(self, user_id: int) -> bool:
        """Забанить"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
            return True
    
    async def unban_user(self, user_id: int) -> bool:
        """Разбанить"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
            return True
    
    async def is_user_banned(self, user_id: int) -> bool:
        """Проверить бан"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return bool(result[0]) if result else False
    
    async def delete_message(self, message_id: int) -> bool:
        """Удалить сообщение"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE messages SET is_deleted = 1 WHERE id = ?", (message_id,))
            await db.commit()
            return True
    
    async def add_admin_log(self, admin_id: int, action: str, target_id: int = None, details: str = None):
        """Лог админа"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                INSERT INTO admin_logs (admin_id, action, target_id, details)
                VALUES (?, ?, ?, ?)
            """, (admin_id, action, target_id, details))
            await db.commit()
    
    async def get_admin_logs(self, limit: int = 50) -> List[Dict]:
        """Получить логи"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT l.id, l.admin_id, l.action, l.target_id, l.details, l.performed_at,
                       a.username, a.first_name
                FROM admin_logs l
                LEFT JOIN users a ON l.admin_id = a.user_id
                ORDER BY l.performed_at DESC
                LIMIT ?
            """, (limit,))
            
            results = await cursor.fetchall()
            return [{"id": r[0], "admin_id": r[1], "action": r[2], "target_id": r[3],
                    "details": r[4], "performed_at": r[5], "admin_username": r[6], 
                    "admin_first_name": r[7]} for r in results]
    
    async def get_all_user_ids(self) -> List[int]:
        """Все ID пользователей"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
            results = await cursor.fetchall()
            return [r[0] for r in results]
EOF
