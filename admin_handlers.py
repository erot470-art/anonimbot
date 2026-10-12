import asyncio
import random
import string
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import Database
from keyboards import get_admin_menu, get_back_keyboard, get_main_menu
from config import ADMIN_ID

admin_router = Router()
db = Database()


class BroadcastStates(StatesGroup):
    message = State()
    confirm = State()


class SearchStates(StatesGroup):
    query = State()


class GiveMoneyStates(StatesGroup):
    amount = State()


def is_admin(uid):
    return uid == ADMIN_ID


@admin_router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=get_admin_menu(), parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    s = await db.get_full_stats()
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего: {s['total_users']}\n"
        f"🆕 За сутки: {s['today_users']}\n"
        f"🚫 Забанено: {s['banned_users']}\n"
        f"💎 Premium: {s['premium_users']}\n\n"
        f"📨 Сообщений: {s['total_messages']}\n"
        f"👁 Раскрыто: {s['revealed_messages']}\n"
        f"📅 Сегодня: {s['today_messages']}\n\n"
        f"👥 Рефералов: {s['total_referrals']}\n"
        f"🎫 Кодов: {s['used_codes']}\n"
        f"💰 Монет в системе: {s['total_balance']:.0f}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())


@admin_router.callback_query(F.data == "admin_top_users")
async def admin_top(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫", show_alert=True)
    top = await db.get_top_receivers(10)
    refs = await db.get_top_referrers(5)
    text = "👥 <b>Топ по сообщениям:</b>\n\n"
    for i, u in enumerate(top, 1):
        name = f"@{u[1]}" if u[1] else u[2] or f"ID{u[0]}"
        text += f"{i}. {name} — {u[3]}\n"
    text += "\n👥 <b>Топ рефереров:</b>\n\n"
    for i, u in enumerate(refs, 1):
        name = f"@{u[1]}" if u[1] else u[2] or f"ID{u[0]}"
        text += f"{i}. {name} — {u[3]}\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())


@admin_router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫", show_alert=True)
    await callback.message.edit_text("🔍 Введи ID или @username:", reply_markup=get_back_keyboard())
    await state.set_state(SearchStates.query)


@admin_router.message(SearchStates.query)
async def admin_search_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    users = await db.search_users(message.text)
    if not users:
        await message.answer("❌ Не найдено", reply_markup=get_admin_menu())
        await state.clear()
        return

    u = users[0]
    text = (
        f"👤 <b>{u[0]}</b>\n"
        f"@{u[1] or 'нет'}\n"
        f"{u[2] or ''} {u[3] or ''}\n"
        f"💰 {u[4]} | 💎 {u[5]} | 🚫 {u[6]}\n"
        f"📨 {u[11]} | 📤 {u[12]}"
    )
    b = InlineKeyboardBuilder()
    if u[6]:
        b.button(text="✅ Разбанить", callback_data=f"admin_unban_{u[0]}")
    else:
        b.button(text="🚫 Забанить", callback_data=f"admin_ban_{u[0]}")
    b.button(text="💰 Выдать монеты", callback_data=f"admin_give_{u[0]}")
    b.button(text="◀️ Назад", callback_data="admin_panel")
    b.adjust(1)
    await message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await state.clear()


@admin_router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    uid = int(callback.data.split("_")[2])
    await db.ban_user(uid)
    await db.add_log(ADMIN_ID, "ban", uid)
    await callback.answer("✅ Забанен", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    uid = int(callback.data.split("_")[2])
    await db.unban_user(uid)
    await db.add_log(ADMIN_ID, "unban", uid)
    await callback.answer("✅ Разбанен", show_alert=True)


@admin_router.callback_query(F.data == "admin_give_money")
async def give_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "💰 Введи: <code>ID сумма</code>\nПример: <code>123456789 100</code>",
        parse_mode="HTML", reply_markup=get_back_keyboard()
    )
    await state.set_state(GiveMoneyStates.amount)


@admin_router.message(GiveMoneyStates.amount)
async def give_money_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        amount = float(parts[1])
        await db.add_balance(uid, amount, "Начисление администратором")
        await db.add_log(ADMIN_ID, "give_money", uid, f"+{amount}")
        await message.answer(f"✅ Начислено {amount} → {uid}", reply_markup=get_admin_menu())
    except:
        await message.answer("❌ Формат: ID сумма", reply_markup=get_admin_menu())
    await state.clear()


@admin_router.callback_query(F.data == "admin_create_code")
async def create_code(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
    ok = await db.create_premium_code(ADMIN_ID, code)
    if ok:
        await db.add_log(ADMIN_ID, "create_code", details=code)
        await callback.message.edit_text(
            f"🎫 <b>Промокод:</b>\n\n<code>{code}</code>",
            parse_mode="HTML", reply_markup=get_admin_menu()
        )
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📢 Введи текст рассылки:", reply_markup=get_back_keyboard())
    await state.set_state(BroadcastStates.message)


@admin_router.message(BroadcastStates.message)
async def broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(text=message.text)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить", callback_data="broadcast_go")
    b.button(text="❌ Отмена", callback_data="admin_panel")
    b.adjust(1)
    await message.answer(
        f"📢 <b>Предпросмотр:</b>\n\n{message.text}\n\nОтправить?",
        parse_mode="HTML", reply_markup=b.as_markup()
    )
    await state.set_state(BroadcastStates.confirm)


@admin_router.callback_query(F.data == "broadcast_go")
async def broadcast_go(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("text", "")
    users = await db.get_all_active_users()
    sent = 0
    failed = 0
    await callback.message.edit_text(f"📢 Рассылка... ({len(users)})")
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>Сообщение от админа:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await db.add_log(ADMIN_ID, "broadcast", details=f"{sent}/{failed}")
    await callback.message.edit_text(
        f"📢 Готово!\n✅ {sent}\n❌ {failed}",
        reply_markup=get_admin_menu()
    )
    await state.clear()


@admin_router.callback_query(F.data == "admin_bans")
async def admin_bans(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    s = await db.get_full_stats()
    await callback.message.edit_text(
        f"🚫 Забанено: {s['banned_users']}\n\n"
        "Используй 🔍 Поиск чтобы найти пользователя и забанить/разбанить",
        reply_markup=get_admin_menu()
    )


@admin_router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    logs = await db.get_logs(30)
    text = "📋 <b>Логи:</b>\n\n"
    for log in logs:
        name = f"@{log[6]}" if log[6] else f"ID{log[1]}"
        text += f"• {log[5][:19]} — {name}: {log[2]}\n"
        if log[3]:
            text += f"   → ID {log[3]}\n"
    await callback.message.edit_text(text or "Пусто", parse_mode="HTML", reply_markup=get_admin_menu())
