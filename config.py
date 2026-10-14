import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_NAME = "/tmp/bot.db"

# ===== АДМИНЫ =====
# Главный админ (может добавлять других админов)
SUPER_ADMIN_ID = int(os.getenv("ADMIN_ID", "8442222382"))

# Список ID админов (можно пополнять через админ-панель)
ADMIN_IDS = [SUPER_ADMIN_ID]

# ===== НАСТРОЙКИ =====
REVEAL_COST = 0          # 0 = бесплатно
REFERRAL_BONUS = 5
PREMIUM_PRICE = 100
MAX_MESSAGE_LENGTH = 500

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")
