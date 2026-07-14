from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import get_admin_menu, get_back_keyboard, get_main_menu
from config import ADMIN_ID
import random
import string

admin_router = Router()
db = Database()

class BroadcastStates(StatesGroup):
    message = State()
    confirm = State()

class SearchStates(StatesGroup):
    query = State()
    user_action = State()

class GiveMoneyStates(StatesGroup):
    user_id = State()
    amount = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ===== АДМИН-ПАНЕЛЬ =====
@admin_router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

# ===== СТАТИСТИКА =====
@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    stats = await db.get_full_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🚫 Забанено: {stats['banned_users']}\n"
        f"💎 Premium: {stats['premium_users']}\n"
        f"🆕 Сегодня: {stats['today_users']}\n\n"
        f"📨 Сообщений всего: {stats['total_messages']}\n"
        f"👁 Раскрыто: {stats['revealed_messages']}\n"
        f"📨 Сегодня: {stats['today_messages']}\n\n"
        f"👥 Рефералов: {stats['total_referrals']}\n"
        f"🎫 Использовано кодов: {stats['used_codes']}\n"
        f"💰 Всего монет: {stats['total_balance']}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())

# ===== ТОП ПОЛЬЗОВАТЕЛЕЙ =====
@admin_router.callback_query(F.data == "admin_top_users")
async def admin_top_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    top_receivers = await db.get_top_receivers(10)
    top_referrers = await db.get_top_referrers(5)
    
    text = "👥 <b>Топ-10 по сообщениям:</b>\n\n"
    for i, user in enumerate(top_receivers, 1):
        name = f"@{user[1]}" if user[1] else user[2] or f"ID{user[0]}"
        text += f"{i}. {name} - {user[3]} всего, {user[4]} за неделю\n"
    
    text += "\n👥 <b>Топ-5 рефереров:</b>\n\n"
    for i, user in enumerate(top_referrers, 1):
        name = f"@{user[1]}" if user[1] else user[2] or f"ID{user[0]}"
        text += f"{i}. {name} - {user[3]} рефералов\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())

# ===== ПОИСК ПОЛЬЗОВАТЕЛЯ =====
@admin_router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    await callback.message.edit_text(
        "🔍 Введите ID пользователя или @username:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SearchStates.query)

@admin_router.message(SearchStates.query)
async def admin_search_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    users = await db.search_users(message.text)
    if users:
        user = users[0]
        is_banned = "🚫 Да" if user[6] else "✅ Нет"
        is_premium = "💎 Да" if user[5] else "❌ Нет"
        
        text = (
            f"👤 <b>Пользователь найден:</b>\n\n"
            f"🆔 ID: {user[0]}\n"
            f"👤 Username: @{user[1] or 'Нет'}\n"
            f"📝 Имя: {user[2] or 'Нет'} {user[3] or ''}\n"
            f"💰 Баланс: {user[4]}\n"
            f"💎 Premium: {is_premium}\n"
            f"🚫 Забанен: {is_banned}\n"
            f"📅 Создан: {user[8]}\n"
            f"📨 Получено: {user[10]}\n"
            f"📤 Отправлено: {user[11]}"
        )
        
        await state.update_data(target_user=user[0])
        builder = InlineKeyboardBuilder()
        if user[6]:
            builder.button(text="✅ Разбанить", callback_data=f"admin_unban_{user[0]}")
        else:
            builder.button(text="🚫 Забанить", callback_data=f"admin_ban_{user[0]}")
        builder.button(text="💰 Выдать монеты", callback_data=f"admin_give_{user[0]}")
        builder.button(text="◀️ Назад", callback_data="admin_panel")
        builder.adjust(1)
        
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.answer("❌ Пользователь не найден", reply_markup=get_admin_menu())
    
    await state.clear()

# ===== БАН/РАЗБАН =====
@admin_router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    user_id = int(callback.data.split("_")[2])
    await db.ban_user(user_id)
    await db.add_log(ADMIN_ID, "ban_user", user_id)
    await callback.answer("✅ Пользователь забанен", show_alert=True)
    await callback.message.delete()

@admin_router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    user_id = int(callback.data.split("_")[2])
    await db.unban_user(user_id)
    await db.add_log(ADMIN_ID, "unban_user", user_id)
    await callback.answer("✅ Пользователь разбанен", show_alert=True)
    await callback.message.delete()

# ===== ВЫДАТЬ МОНЕТЫ =====
@admin_router.callback_query(F.data.startswith("admin_give_"))
async def admin_give_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    user_id = int(callback.data.split("_")[2])
    await state.update_data(target_user=user_id)
    await callback.message.answer("💰 Введите сумму для начисления:", reply_markup=get_back_keyboard())
    await state.set_state(GiveMoneyStates.amount)

@admin_router.message(GiveMoneyStates.amount)
async def admin_give_money_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        amount = float(message.text)
        data = await state.get_data()
        user_id = data['target_user']
        
        await db.add_balance(user_id, amount, f"Начисление от администратора")
        await db.add_log(ADMIN_ID, "give_money", user_id, f"Amount: {amount}")
        await message.answer(f"✅ Начислено {amount} монет пользователю {user_id}", reply_markup=get_admin_menu())
    except ValueError:
        await message.answer("❌ Введите число!", reply_markup=get_admin_menu())
    
    await state.clear()

# ===== РАССЫЛКА =====
@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    await callback.message.edit_text(
        "📢 Введите текст для рассылки:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(BroadcastStates.message)

@admin_router.message(BroadcastStates.message)
async def broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(broadcast_text=message.text)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data="broadcast_confirm")
    builder.button(text="❌ Отмена", callback_data="admin_panel")
    builder.adjust(1)
    
    await message.answer(
        f"📢 <b>Предпросмотр рассылки:</b>\n\n{message.text}\n\nОтправить всем пользователям?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BroadcastStates.confirm)

@admin_router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    
    data = await state.get_data()
    text = data.get('broadcast_text', '')
    
    users = await db.get_all_active_users()
    sent_count = 0
    failed_count = 0
    
    await callback.message.edit_text(f"📢 Рассылка начата... ({len(users)} пользователей)")
    
    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 <b>Сообщение от администратора:</b>\n\n{text}", parse_mode="HTML")
            sent_count += 1
            await asyncio.sleep(0.05)  # Чтобы не превысить лимиты
        except:
            failed_count += 1
    
    await db.add_log(ADMIN_ID, "broadcast", details=f"Sent: {sent_count}, Failed: {failed_count}")
    await callback.message.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n✅ Отправлено: {sent_count}\n❌ Не доставлено: {failed_count}",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )
    await state.clear()

# ===== ПРОМОКОДЫ =====
@admin_router.callback_query(F.data == "admin_create_code")
async def admin_create_code(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    await db.create_premium_code(ADMIN_ID, code)
    await db.add_log(ADMIN_ID, "create_code", details=f"Code: {code}")
    
    await callback.message.edit_text(
        f"🎫 <b>Новый промокод создан:</b>\n\n<code>{code}</code>\n\n"
        f"Отправьте его пользователю для активации Premium",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )

# ===== ЛОГИ =====
@admin_router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    
    logs = await db.get_logs(30)
    text = "📋 <b>Последние действия администраторов:</b>\n\n"
    
    if logs:
        for log in logs:
            admin_name = f"@{log[6]}" if log[6] else f"ID{log[1]}"
            text += f"• {log[5]} - {admin_name}: {log[2]}"
            if log[3]:
                text += f" (ID: {log[3]})"
            if log[4]:
                text += f" - {log[4]}"
            text += "\n"
    else:
        text += "Логов пока нет"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())

# ===== ЗАКРЫТЬ =====
@admin_router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu(callback.from_user.id, is_admin(callback.from_user.id))
    )

# Импорт asyncio для рассылки
import asyncio
from aiogram.utils.keyboard import InlineKeyboardBuilder
