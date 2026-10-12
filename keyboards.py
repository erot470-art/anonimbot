from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def get_main_menu(user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Моя ссылка", callback_data="my_link")
    b.button(text="👤 Профиль", callback_data="profile")
    b.button(text="👥 Рефералы", callback_data="referrals")
    b.button(text="💎 Premium", callback_data="premium")
    b.button(text="📨 Входящие", callback_data="inbox")
    b.button(text="📤 Исходящие", callback_data="outbox")
    b.button(text="⭐ Избранное", callback_data="favorites")
    b.button(text="❓ Помощь", callback_data="help")
    if is_admin:
        b.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    b.adjust(2)
    return b.as_markup()


def get_message_keyboard(message_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👁 Узнать отправителя", callback_data=f"reveal_{message_id}")
    b.button(text="⭐ В избранное", callback_data=f"fav_{message_id}")
    b.button(text="🗑 Удалить", callback_data=f"delete_{message_id}")
    b.adjust(1)
    return b.as_markup()


def get_profile_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 История операций", callback_data="transactions")
    b.button(text="💎 Купить Premium", callback_data="buy_premium")
    b.button(text="◀️ Назад", callback_data="back_main")
    b.adjust(1)
    return b.as_markup()


def get_admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="admin_stats")
    b.button(text="👥 Топ пользователей", callback_data="admin_top_users")
    b.button(text="🔍 Поиск", callback_data="admin_search")
    b.button(text="📢 Рассылка", callback_data="admin_broadcast")
    b.button(text="🎫 Промокод", callback_data="admin_create_code")
    b.button(text="🚫 Баны", callback_data="admin_bans")
    b.button(text="💰 Выдать монеты", callback_data="admin_give_money")
    b.button(text="📋 Логи", callback_data="admin_logs")
    b.button(text="◀️ В меню", callback_data="back_main")
    b.adjust(2)
    return b.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data="back_main")
    return b.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="cancel_action")
    return b.as_markup()
