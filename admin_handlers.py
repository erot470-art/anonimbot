from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import *
from config import ADMIN_ID
import random
import string

admin_router = Router()
db = Database()

class Broadcast(StatesGroup):
    message = State()
    confirm = State()

class SearchUser(StatesGroup):
    query = State()

def is_admin(user_id):
    return user_id == ADMIN_ID

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    stats = await db.get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"💎 Premium: {stats['premium_users']}\n"
        f"📨 Сообщений: {stats['total_messages']}\n"
        f"👁 Раскрыто: {stats['revealed_messages']}\n"
        f"👥 Рефералов: {stats['total_referrals']}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

@admin_router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    top = await db.get_top_users(15)
    text = "👥 <b>Топ пользователей:</b>\n\n"
    for i, user in enumerate(top, 1):
        name = f"@{user[1]}" if user[1] else user[2]
        text += f"{i}. {name} - {user[3]} сообщ.\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

@admin_router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    await callback.message.edit_text("🔍 Введи ID или @username:", reply_markup=get_admin_keyboard())
    await state.set_state(SearchUser.query)

@admin_router.message(SearchUser.query)
async def admin_search_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    users = await db.search_users(message.text)
    if users:
        text = "🔍 <b>Результаты поиска:</b>\n\n"
        for user in users[:5]:
            name = f"@{user[1]}" if user[1] else user[2]
            text += f"🆔 {user[0]} - {name}\n"
            text += f"💰 {user[4]} монет | 💎 {'Да' if user[5] else 'Нет'}\n\n"
    else:
        text = "❌ Ничего не найдено"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await state.clear()

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    await callback.message.edit_text("📢 Введи текст рассылки:", reply_markup=get_admin_keyboard())
    await state.set_state(Broadcast.message)

@admin_router.message(Broadcast.message)
async def broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(message=message.text)
    await message.answer(f"📢 Рассылка:\n\n{message.text}\n\nОтправить?", reply_markup=get_admin_keyboard())
    await state.set_state(Broadcast.confirm)

@admin_router.callback_query(F.data == "admin_codes")
async def admin_codes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    await db.create_premium_code(code, ADMIN_ID)
    await callback.message.edit_text(
        f"🎫 Новый промокод:\n<code>{code}</code>",
        parse_mode="HTML", reply_markup=get_admin_keyboard()
    )

@admin_router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    logs = await db.get_logs(20)
    text = "📋 <b>Последние действия:</b>\n\n"
    for log in logs:
        text += f"• {log[2]} - {log[6]}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

@admin_router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    await callback.message.delete()
