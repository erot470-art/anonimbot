import asyncio
import random
import string
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import Database
from keyboards import get_admin_menu, get_back_keyboard, get_admins_manage_keyboard
from utils import is_admin, is_super_admin
from config import SUPER_ADMIN_ID

admin_router = Router()
db = Database()


class AdminStates(StatesGroup):
    broadcast_msg = State()
    broadcast_confirm = State()
    search_query = State()
    give_money = State()
    add_admin = State()
    remove_admin = State()


# ===== ОБЩАЯ ПРОВЕРКА =====
async def check_admin(callback_or_msg) -> bool:
    user_id = callback_or_msg.from_user.id
    return await is_admin(user_id)


# ===== АДМИН-ПАНЕЛЬ =====
@admin_router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not await check_admin(callback):
        return await callback.answer("🚫 Нет доступа", show_alert=True)
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=get_admin_menu(super_admin), parse_mode="HTML"
    )


# ===== СТАТИСТИКА =====
@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not await check_admin(callback):
        return await callback.answer("🚫", show_alert=True)
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
        f"💰 Монет: {s['total_balance']:.0f}"
    )
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu(super_admin))


# ===== ТОП ПОЛЬЗОВАТЕЛЕЙ =====
@admin_router.callback_query(F.data == "admin_top_users")
async def admin_top(callback: CallbackQuery):
    if not await check_admin(callback):
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
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu(super_admin))


# ===== ПОИСК =====
@admin_router.callback_query(F.data == "admin_search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return await callback.answer("🚫", show_alert=True)
    await callback.message.edit_text("🔍 Введи ID или @username:", reply_markup=get_back_keyboard())
    await state.set_state(AdminStates.search_query)


@admin_router.message(AdminStates.search_query)
async def admin_search_result(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    users = await db.search_users(message.text)
    if not users:
        await message.answer("❌ Не найдено", reply_markup=get_admin_menu(await is_super_admin(message.from_user.id)))
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
    if not await check_admin(callback):
        return
    uid = int(callback.data.split("_")[2])
    if uid == SUPER_ADMIN_ID:
        return await callback.answer("❌ Нельзя забанить главного админа", show_alert=True)
    await db.ban_user(uid)
    await db.add_log(callback.from_user.id, "ban", uid)
    await callback.answer("✅ Забанен", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    uid = int(callback.data.split("_")[2])
    await db.unban_user(uid)
    await db.add_log(callback.from_user.id, "unban", uid)
    await callback.answer("✅ Разбанен", show_alert=True)


# ===== ВЫДАТЬ МОНЕТЫ =====
@admin_router.callback_query(F.data == "admin_give_money")
async def give_money_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "💰 Введи: <code>ID сумма</code>\nПример: <code>123456789 100</code>",
        parse_mode="HTML", reply_markup=get_back_keyboard()
    )
    await state.set_state(AdminStates.give_money)


@admin_router.message(AdminStates.give_money)
async def give_money_amount(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        amount = float(parts[1])
        await db.add_balance(uid, amount, "Начисление администратором")
        await db.add_log(message.from_user.id, "give_money", uid, f"+{amount}")
        super_admin = await is_super_admin(message.from_user.id)
        await message.answer(f"✅ Начислено {amount} → {uid}", reply_markup=get_admin_menu(super_admin))
    except:
        super_admin = await is_super_admin(message.from_user.id)
        await message.answer("❌ Формат: ID сумма", reply_markup=get_admin_menu(super_admin))
    await state.clear()


# ===== ПРОМОКОДЫ =====
@admin_router.callback_query(F.data == "admin_create_code")
async def create_code(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
    ok = await db.create_premium_code(callback.from_user.id, code)
    if ok:
        await db.add_log(callback.from_user.id, "create_code", details=code)
        super_admin = await is_super_admin(callback.from_user.id)
        await callback.message.edit_text(
            f"🎫 <b>Промокод:</b>\n\n<code>{code}</code>",
            parse_mode="HTML", reply_markup=get_admin_menu(super_admin)
        )
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


# ===== РАССЫЛКА =====
@admin_router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await callback.message.edit_text("📢 Введи текст рассылки:", reply_markup=get_back_keyboard())
    await state.set_state(AdminStates.broadcast_msg)


@admin_router.message(AdminStates.broadcast_msg)
async def broadcast_preview(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
    await state.set_state(AdminStates.broadcast_confirm)


@admin_router.callback_query(F.data == "broadcast_go")
async def broadcast_go(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_admin(callback):
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
    await db.add_log(callback.from_user.id, "broadcast", details=f"{sent}/{failed}")
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(
        f"📢 Готово!\n✅ {sent}\n❌ {failed}",
        reply_markup=get_admin_menu(super_admin)
    )
    await state.clear()


# ===== БАНЫ =====
@admin_router.callback_query(F.data == "admin_bans")
async def admin_bans(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    s = await db.get_full_stats()
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(
        f"🚫 Забанено: {s['banned_users']}\n\n"
        "Используй 🔍 Поиск чтобы найти пользователя",
        reply_markup=get_admin_menu(super_admin)
    )


# ===== ЛОГИ =====
@admin_router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    logs = await db.get_logs(30)
    text = "📋 <b>Логи:</b>\n\n"
    for log in logs:
        name = f"@{log[6]}" if log[6] else f"ID{log[1]}"
        text += f"• {str(log[5])[:19]} — {name}: {log[2]}\n"
        if log[3]:
            text += f"   → ID {log[3]}\n"
    super_admin = await is_super_admin(callback.from_user.id)
    await callback.message.edit_text(text or "Пусто", parse_mode="HTML", reply_markup=get_admin_menu(super_admin))


# ==================== УПРАВЛЕНИЕ АДМИНАМИ (ТОЛЬКО ДЛЯ ГЛАВНОГО) ====================
@admin_router.callback_query(F.data == "admin_manage_admins")
async def manage_admins(callback: CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        return await callback.answer("🚫 Только для главного админа", show_alert=True)
    await callback.message.edit_text(
        "👑 <b>Управление админами</b>\n\nВыбери действие:",
        reply_markup=get_admins_manage_keyboard(), parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_list_admins")
async def list_admins(callback: CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        return await callback.answer("🚫", show_alert=True)

    admins = await db.get_all_admins()
    text = f"👑 <b>Список админов:</b>\n\n"
    text += f"• <b>Главный:</b> <code>{SUPER_ADMIN_ID}</code>\n\n"
    text += "<b>Дополнительные:</b>\n"
    if admins:
        for a in admins:
            user = await db.get_user(a)
            name = f"@{user[1]}" if user and user[1] else f"ID{a}"
            text += f"• {name} — <code>{a}</code>\n"
    else:
        text += "Пусто\n"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admins_manage_keyboard())


@admin_router.callback_query(F.data == "admin_add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await is_super_admin(callback.from_user.id):
        return await callback.answer("🚫", show_alert=True)
    await callback.message.edit_text(
        "👑 Введи ID пользователя, которого хочешь назначить админом:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(AdminStates.add_admin)


@admin_router.message(AdminStates.add_admin)
async def add_admin_finish(message: Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        if uid == SUPER_ADMIN_ID:
            await message.answer("❌ Это уже главный админ")
            await state.clear()
            return

        if await db.is_admin_in_db(uid):
            await message.answer("⚠️ Уже админ")
            await state.clear()
            return

        ok = await db.add_admin(uid, message.from_user.id)
        if ok:
            await db.add_log(message.from_user.id, "add_admin", uid)
            await message.answer(
                f"✅ Пользователь <code>{uid}</code> назначен админом!",
                parse_mode="HTML"
            )
            # Уведомляем нового админа
            try:
                await message.bot.send_message(
                    uid,
                    "👑 <b>Поздравляем!</b>\n\nТебе выданы права администратора бота.\n"
                    "Команда для входа: /admin",
                    parse_mode="HTML"
                )
            except:
                pass
        else:
            await message.answer("❌ Ошибка")
    except:
        await message.answer("❌ Введи корректный ID (число)")
    await state.clear()
    await message.answer("⚙️ Админ-панель:", reply_markup=get_admins_manage_keyboard())


@admin_router.callback_query(F.data == "admin_remove_admin")
async def remove_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await is_super_admin(callback.from_user.id):
        return await callback.answer("🚫", show_alert=True)
    admins = await db.get_all_admins()
    if not admins:
        return await callback.answer("Нет доп. админов", show_alert=True)
    text = "👑 <b>Введи ID админа для удаления:</b>\n\n"
    for a in admins:
        text += f"• <code>{a}</code>\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    await state.set_state(AdminStates.remove_admin)


@admin_router.message(AdminStates.remove_admin)
async def remove_admin_finish(message: Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        if uid == SUPER_ADMIN_ID:
            await message.answer("❌ Нельзя удалить главного админа")
            await state.clear()
            return
        await db.remove_admin(uid)
        await db.add_log(message.from_user.id, "remove_admin", uid)
        await message.answer(f"✅ Админ <code>{uid}</code> удалён", parse_mode="HTML")
        try:
            await message.bot.send_message(uid, "❌ Твои права администратора отозваны.")
        except:
            pass
    except:
        await message.answer("❌ Некорректный ID")
    await state.clear()
    await message.answer("⚙️ Управление админами:", reply_markup=get_admins_manage_keyboard())
