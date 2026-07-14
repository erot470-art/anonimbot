from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Моя ссылка", callback_data="my_link")
    builder.button(text="📊 Профиль", callback_data="profile")
    builder.button(text="👥 Рефералы", callback_data="referrals")
    builder.button(text="💎 Премиум", callback_data="premium")
    builder.button(text="📨 Мои сообщения", callback_data="my_messages")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()

def get_reveal_keyboard(msg_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Узнать отправителя", callback_data=f"reveal_{msg_id}")
    builder.button(text="❌ Удалить", callback_data=f"delete_{msg_id}")
    builder.button(text="⭐ В избранное", callback_data=f"fav_{msg_id}")
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    return builder.as_markup()

def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="🔍 Поиск", callback_data="admin_search")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎫 Промокоды", callback_data="admin_codes")
    builder.button(text="📋 Логи", callback_data="admin_logs")
    builder.button(text="❌ Закрыть", callback_data="admin_close")
    builder.adjust(2)
    return builder.as_markup()

def get_profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить", callback_data="deposit")
    builder.button(text="💎 Купить премиум", callback_data="buy_premium")
    builder.button(text="🎫 Активировать код", callback_data="activate_code")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()
