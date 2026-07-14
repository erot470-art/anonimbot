from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from database import Database
from keyboards import (
    get_admin_main_keyboard, 
    get_admin_back_keyboard,
    get_user_actions_keyboard,
    get_broadcast_keyboard
)
from config import ADMIN_ID

# Инициализация роутера и базы данных
admin_router = Router()
db = Database()


# Состояния для FSM (машины состояний)
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm_broadcast = State()


class SearchStates(StatesGroup):
    waiting_for_query = State()


# Фильтр для проверки админа
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ===== ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ =====

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Показ статистики бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа", show_alert=True)
        return
    
    stats = await db.get_total_stats()
    
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📨 Всего сообщений: <b>{stats['total_messages']}</b>\n"
        f"👁 Раскрыто сообщений: <b>{stats['revealed_messages']}</b>\n\n"
        f"📅 За сегодня:\n"
        f"• Новых пользователей: <b>{stats['today_users']}</b>\n"
        f"• Сообщений: <b>{stats['today_messages']}</b>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_top_users")
async def admin_top_users(callback: CallbackQuery):
    """Показ топ-10 пользователей по сообщениям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа", show_alert=True)
        return
    
    top_users = await db.get_top_users(10)
    
    if not top_users:
        await callback.message.edit_text(
            "📊 <b>Топ пользователей</b>\n\nПока нет данных.",
            reply_markup=get_admin_back_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "👥 <b>Топ-10 пользователей по сообщениям</b>\n\n"
    
    for i, user in enumerate(top_users, 1):
        display_name = user['username'] or user['first_name'] or f"ID: {user['user_id']}"
        if user['username']:
            display_name = f"@{user['username']}"
        
        text += f"{i}. {display_name}: <b>{user['msg_count']}</b> сообщ.\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    """Начало поиска пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите ID пользователя или @username:",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.waiting_for_query)
    await callback.answer()


@admin_router.message(SearchStates.waiting_for_query)
async def admin_search_result(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        await state.clear()
        return
    
   
