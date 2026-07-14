import aiosqlite
import os
from typing import Optional, Tuple, List, Dict
from config import DATABASE_NAME


class Database:
    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        
    async def create_tables(self):
        """Создание таблиц в базе данных"""
        # Убеждаемся, что директория существует
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        async with aiosqlite.connect(self.db_name) as db:
            # Включаем поддержку внешних ключей
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Таблица пользователей
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
            
            # Таблица сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    receiver_message_id INTEGER,
                    message_type TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_revealed INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (sender_id) REFERENCES users(user_id),
                    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица баланса
            await db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id INTEGER PRIMARY KEY,
                    amount REAL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица логов администратора
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
            
            # Индексы для оптимизации
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_receiver 
                ON messages(receiver_id, sent_at)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_sender 
                ON messages(sender_id, sent_at)
            """)
            
            await db.commit()
    
    # ... остальные методы остаются без изменений ...
