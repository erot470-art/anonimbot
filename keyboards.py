from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_main_menu(user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Моя ссылка", callback_data="my_link")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="👥 Рефералы", callback_data="referrals")
    builder.button(text="💎 Premium", callback_data="premium")
    builder.button(text="📨 Входящие", callback_data="inbox")
    builder.button(text="📤 Исходящие", callback_data="outbox")
    builder.button(text="⭐ Избранное", callback_data="favorites")
    builder.button(text="📝 Написать", callback_data="compose")
    if is_admin:
        builder.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()

def get_message_keyboard(message_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Узнать отправителя", callback_data=f"reveal_{message_id}")
    builder.button(text="⭐ В избранное", callback_data=f"fav_{message_id}")
    builder.button(text="💬 Ответить", callback_data=f"reply_{message_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete_{message_id}")
    builder.button(text="📋 Содержание", callback_data=f"content_{message_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_profile_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 История операций", callback_data="transactions")
    builder.button(text="💎 Купить Premium", callback_data="buy_premium")
    builder.button(text="🎫 Активировать промокод", callback_data="activate_code")
    builder.button(text="◀️ Назад", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Топ пользователей", callback_data="admin_top_users")
    builder.button(text="🔍 Поиск пользователя", callback_data="admin_search")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎫 Создать промокод", callback_data="admin_create_code")
    builder.button(text="👁 Все промокоды", callback_data="admin_list_codes")
    builder.button(text="🚫 Управление банами", callback_data="admin_bans")
    builder.button(text="💰 Выдать монеты", callback_data="admin_give_money")
    builder.button(text="📋 Логи", callback_data="admin_logs")
    builder.button(text="◀️ Назад в меню", callback_data="back_main")
    builder.adjust(2)
    return builder.as_markup()

def get_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_main")
    return builder.as_markup()

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_action")
    return builder.as_markup()

def get_navigation_keyboard(current_page: int, total_pages: int, callback_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current_page > 0:
        builder.button(text="◀️ Назад", callback_data=f"{callback_prefix}_{current_page-1}")
    builder.button(text=f"{current_page+1}/{total_pages}", callback_data="ignore")
    if current_page < total_pages - 1:
        builder.button(text="Вперед ▶️", callback_data=f"{callback_prefix}_{current_page+1}")
    builder.button(text="🏠 Главная", callback_data="back_main")
    builder.adjust(3, 1)
    return builder.as_markup()
