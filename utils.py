from config import SUPER_ADMIN_ID, ADMIN_IDS
from database import Database

db = Database()


async def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    if user_id == SUPER_ADMIN_ID:
        return True
    if user_id in ADMIN_IDS:
        return True
    return await db.is_admin_in_db(user_id)


async def is_super_admin(user_id: int) -> bool:
    """Проверка является ли пользователь ГЛАВНЫМ админом"""
    return user_id == SUPER_ADMIN_ID


async def can_reveal_sender(user_id: int) -> tuple:
    """Можно ли раскрыть отправителя"""
    return True, "OK"


def get_user_display_name(user_info: tuple) -> str:
    """Форматирование имени"""
    if not user_info:
        return "Пользователь"
    username = user_info[1] if len(user_info) > 1 else None
    first_name = user_info[2] if len(user_info) > 2 else None
    if username:
        return f"@{username}"
    return first_name or "Пользователь"
