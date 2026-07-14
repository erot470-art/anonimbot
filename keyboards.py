from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_keyboard():
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Получить мою ссылку", callback_data="get_link")
    builder.button(text="❓ Как это работает", callback_data="how_it_works")
    builder.adjust(1)
    return builder.as_markup()


def get_reveal_keyboard(message_id: int):
    """Клавиатура с кнопкой раскрытия личности"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👁 Узнать отправителя", 
        callback_data=f"reveal_{message_id}"
    )
    return builder.as_markup()


def get_back_keyboard():
    """Клавиатура возврата в меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В главное меню", callback_data="back_to_menu")
    return builder.as_markup()


# ===== АДМИН-КЛАВИАТУРЫ =====

def get_admin_main_keyboard():
    """Главное меню администратора"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Топ пользователей", callback_data="admin_top_users")
    builder.button(text="🔍 Поиск пользователя", callback_data="admin_search")
    builder.button(text="📋 Логи действий", callback_data="admin_logs")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="❌ Закрыть", callback_data="admin_close")
    builder.adjust(2)
    return builder.as_markup()


def get_admin_back_keyboard():
    """Клавиатура возврата в админ-меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад в админ-панель", callback_data="admin_back")
    builder.button(text="❌ Закрыть", callback_data="admin_close")
    builder.adjust(1)
    return builder.as_markup()


def get_user_actions_keyboard(user_id: int, is_banned: bool = False):
    """Клавиатура действий с пользователем"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📨 Сообщения", callback_data=f"admin_user_msgs_{user_id}")
    
    if is_banned:
        builder.button(text="✅ Разбанить", callback_data=f"admin_unban_{user_id}")
    else:
        builder.button(text="🚫 Забанить", callback_data=f"admin_ban_{user_id}")
    
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(2)
    return builder.as_markup()


def get_broadcast_keyboard():
    """Клавиатура для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить рассылку", callback_data="admin_confirm_broadcast")
    builder.button(text="❌ Отменить", callback_data="admin_cancel_broadcast")
    builder.adjust(1)
    return builder.as_markup()
