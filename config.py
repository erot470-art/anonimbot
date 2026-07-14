import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администратора
ADMIN_ID = int(os.getenv("ADMIN_ID", "8442222382"))

# Настройки базы данных (на Render используем постоянное хранилище)
DATABASE_NAME = os.getenv("DATABASE_NAME", "/opt/render/project/src/anonymous_bot.db")

# Стоимость раскрытия личности
REVEAL_COST = float(os.getenv("REVEAL_COST", "0"))
