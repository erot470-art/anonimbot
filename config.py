import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8442222382"))
DATABASE_NAME = "/tmp/bot.db"
REVEAL_COST = 0          # 0 = раскрытие бесплатное для всех
REFERRAL_BONUS = 5
PREMIUM_PRICE = 100
MAX_MESSAGE_LENGTH = 500

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")
