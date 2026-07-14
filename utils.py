from database import Database
from config import REVEAL_COST

# Инициализация базы данных
db = Database()


async def can_reveal_sender(user_id: int) -> tuple[bool, str]:
    """
    Проверка возможности раскрытия личности отправителя.
    
    ЭТА ФУНКЦИЯ - ЗАГЛУШКА. Здесь вы можете легко добавить:
    - Проверку баланса пользователя
    - Проверку подписки на канал
    - Проверку наличия VIP-статуса
    - И любые другие условия
    
    Возвращает:
    - bool: True если можно раскрыть, False если нет
    - str: Сообщение с причиной отказа или успеха
    """
    
    # ПРИМЕР 1: Проверка подписки на канал (заглушка)
    # from aiogram import Bot
    # bot = Bot.get_current()
    # try:
    #     member = await bot.get_chat_member(chat_id="@your_channel", user_id=user_id)
    #     if member.status not in ["creator", "administrator", "member"]:
    #         return False, "❌ Для раскрытия личности нужна подписка на канал @your_channel"
    # except:
    #     return False, "❌ Ошибка проверки подписки"
    
    # ПРИМЕР 2: Проверка баланса (заглушка)
    # async with aiosqlite.connect(DATABASE_NAME) as db:
    #     cursor = await db.execute("SELECT amount FROM balances WHERE user_id = ?", (user_id,))
    #     result = await cursor.fetchone()
    #     balance = result[0] if result else 0
    #     
    #     if balance < REVEAL_COST:
    #         return False, f"❌ Недостаточно средств. Нужно: {REVEAL_COST} монет. Ваш баланс: {balance} монет"
    #     
    #     # Списываем средства
    #     await db.execute("UPDATE balances SET amount = amount - ? WHERE user_id = ?", 
    #                     (REVEAL_COST, user_id))
    #     await db.commit()
    
    # ПРИМЕР 3: Бесплатное раскрытие для всех (текущая реализация)
    return True, "✅ Личность отправителя будет раскрыта бесплатно"


def get_user_display_name(user_info: tuple) -> str:
    """
    Формирование отображаемого имени пользователя
    """
    username, first_name, last_name = user_info
    
    if username:
        return f"@{username}"
    
    display_name = first_name or ""
    if last_name:
        display_name += f" {last_name}"
    
    return display_name.strip() or "Пользователь без имени"


def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для Markdown
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
