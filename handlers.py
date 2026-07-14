from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link, decode_payload
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import *
from config import ADMIN_ID, REFERRAL_BONUS, REVEAL_COST, PREMIUM_PRICE
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# Временное хранилище состояний отправки
pending_messages = {}  # {user_id: receiver_id}

class ComposeStates(StatesGroup):
    waiting_for_user = State()
    waiting_for_message = State()

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    referrer = None
    
    # Проверяем реферала
    if len(args) > 1:
        try:
            referrer = int(args[1])
            if referrer == user_id:
                referrer = None
        except:
            pass
    
    # Регистрируем пользователя
    is_new = await db.register_user(
        user_id, 
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        referrer
    )
    
    # Начисляем бонус за реферала
    if referrer and is_new:
        success, msg = await db.add_referral(referrer, user_id)
        if success:
            try:
                await bot.send_message(referrer, f"🎉 Новый реферал! +{REFERRAL_BONUS} монет")
            except:
                pass
    
    # Проверяем бан
    if await db.is_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован.")
        return
    
    is_admin = (user_id == ADMIN_ID)
    
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\n"
        "🔒 Отправляй и получай анонимные сообщения\n"
        "👁 Раскрывай отправителей\n"
        "💰 Зарабатывай на рефералах\n"
        "💎 Premium статус\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu(user_id, is_admin),
        parse_mode="HTML"
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=get_admin_menu(), parse_mode="HTML")
    else:
        await message.answer("🚫 Доступ запрещен")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in pending_messages:
        del pending_messages[user_id]
    await state.clear()
    is_admin = (user_id == ADMIN_ID)
    await message.answer("❌ Действие отменено", reply_markup=get_main_menu(user_id, is_admin))

# ===== ГЛАВНОЕ МЕНЮ =====
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = (user_id == ADMIN_ID)
    if user_id in pending_messages:
        del pending_messages[user_id]
    await callback.message.edit_text(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id, is_admin)
    )

@router.callback_query(F.data == "my_link")
async def my_link(callback: CallbackQuery):
    link = await create_start_link(callback.bot, str(callback.from_user.id), encode=True)
    await callback.message.edit_text(
        f"🔗 <b>Твоя персональная ссылка:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Отправь её друзьям!\n"
        f"💰 Получай +{REFERRAL_BONUS} монет за каждого друга\n"
        f"📨 Они смогут отправлять тебе анонимные сообщения",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "profile")
async def show_profile_callback(callback: CallbackQuery):
    await show_profile(callback.message)
    await callback.answer()

async def show_profile(message: Message):
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    balance = user[4]
    is_premium = "💎 Да" if user[5] else "❌ Нет"
    is_banned = "🚫 Да" if user[6] else "✅ Нет"
    ref_count = await db.get_referral_count(user_id)
    
    text = (
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 Username: @{user[1] or 'не указан'}\n"
        f"📝 Имя: {user[2] or 'не указано'} {user[3] or ''}\n"
        f"💰 Баланс: <b>{balance} монет</b>\n"
        f"💎 Premium: {is_premium}\n"
        f"🚫 Статус: {is_banned}\n"
        f"👥 Рефералов: <b>{ref_count}</b>\n"
        f"📨 Получено сообщений: <b>{user[10]}</b>\n"
        f"📤 Отправлено сообщений: <b>{user[11]}</b>\n"
        f"📅 Дата регистрации: {user[9] or 'неизвестно'}"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "transactions")
async def show_transactions(callback: CallbackQuery):
    transactions = await db.get_transactions(callback.from_user.id, 15)
    text = "💰 <b>История операций:</b>\n\n"
    
    if transactions:
        for tx in transactions:
            emoji = "✅" if tx[3] == "credit" else "❌"
            text += f"{emoji} {tx[2]:+.0f} монет - {tx[4]}\n"
            text += f"   📅 {tx[5]}\n"
    else:
        text += "Операций пока нет"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    referrals = await db.get_referrals(user_id)
    count = len(referrals)
    earnings = await db.get_referral_earnings(user_id)
    
    text = f"👥 <b>Твои рефералы ({count})</b>\n"
    text += f"💰 Заработано: <b>{earnings} монет</b>\n\n"
    
    if referrals:
        for i, ref in enumerate(referrals[:20], 1):
            name = f"@{ref[5]}" if ref[5] else ref[6] or f"ID{ref[2]}"
            bonus = "✅" if ref[3] else "⏳"
            text += f"{i}. {name} {bonus}\n"
        
        if count > 20:
            text += f"\n... и еще {count - 20}"
    else:
        text += "У тебя пока нет рефералов\n\n"
        text += "🔗 Поделись своей ссылкой из меню!\n"
        text += f"💰 Получи {REFERRAL_BONUS} монет за каждого друга"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    is_prem = await db.is_premium(callback.from_user.id)
    
    if is_prem:
        text = (
            "💎 <b>У тебя Premium статус!</b>\n\n"
            "✅ Бесплатное раскрытие отправителей\n"
            "✅ Приоритетная поддержка\n"
            "✅ Увеличенный лимит сообщений\n"
            "✅ Эксклюзивные функции"
        )
    else:
        text = (
            "💎 <b>Premium статус</b>\n\n"
            "Преимущества:\n"
            "✅ Бесплатное раскрытие отправителей\n"
            "✅ Приоритетная поддержка\n"
            "✅ Увеличенный лимит сообщений\n"
            "✅ Эксклюзивные функции\n\n"
            f"💰 Стоимость: <b>{PREMIUM_PRICE} монет</b>\n"
            f"💳 Твой баланс: <b>{await db.get_balance(callback.from_user.id)} монет</b>"
        )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    success, msg = await db.buy_premium(callback.from_user.id)
    await callback.answer(msg, show_alert=True)
    if success:
        await db.add_log(ADMIN_ID, "buy_premium", callback.from_user.id)
        await show_premium(callback)

@router.callback_query(F.data == "activate_code")
async def activate_code_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎫 <b>Введи промокод:</b>\n\nОтправь код в чат:",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await state.set_state("waiting_for_code")

@router.message(F.text, F.state == "waiting_for_code")
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    success, msg = await db.use_premium_code(message.from_user.id, code)
    await message.answer(msg, reply_markup=get_main_menu(message.from_user.id, message.from_user.id == ADMIN_ID))
    await state.clear()

# ===== СООБЩЕНИЯ =====
@router.callback_query(F.data == "inbox")
async def show_inbox(callback: CallbackQuery):
    messages = await db.get_received_messages(callback.from_user.id, 20)
    
    if not messages:
        await callback.message.edit_text(
            "📨 <b>Входящие сообщения</b>\n\nУ тебя пока нет сообщений\n\n"
            "🔗 Поделись ссылкой с друзьями!",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "📨 <b>Входящие сообщения:</b>\n\n"
    for msg in messages:
        sender = "Аноним" if msg[5] else (f"@{msg[9]}" if msg[9] else msg[10] or "Пользователь")
        status = "👁" if msg[7] else "🔒"
        fav = "⭐" if msg[8] else ""
        msg_type = {"text": "📝", "photo": "🖼", "voice": "🎤", "video_note": "🎥"}.get(msg[3], "📨")
        text += f"{msg_type} {status} {fav} От: {sender}\n"
        text += f"   📅 {msg[10]}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "outbox")
async def show_outbox(callback: CallbackQuery):
    messages = await db.get_sent_messages(callback.from_user.id, 20)
    
    if not messages:
        await callback.message.edit_text(
            "📤 <b>Исходящие сообщения</b>\n\nТы еще никому не писал",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "📤 <b>Исходящие сообщения:</b>\n\n"
    for msg in messages:
        receiver = f"@{msg[9]}" if msg[9] else msg[10] or f"ID{msg[2]}"
        status = "👁" if msg[7] else "🔒"
        msg_type = {"text": "📝", "photo": "🖼", "voice": "🎤", "video_note": "🎥"}.get(msg[3], "📨")
        text += f"{msg_type} {status} Кому: {receiver}\n"
        text += f"   📅 {msg[10]}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "favorites")
async def show_favorites(callback: CallbackQuery):
    messages = await db.get_favorite_messages(callback.from_user.id, 20)
    
    if not messages:
        await callback.message.edit_text(
            "⭐ <b>Избранное</b>\n\nНет избранных сообщений",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "⭐ <b>Избранные сообщения:</b>\n\n"
    for msg in messages:
        sender = f"@{msg[9]}" if msg[9] else msg[10] or "Пользователь"
        text += f"От: {sender}\n"
        if msg[4]:
            text += f"📝 {msg[4][:100]}...\n" if len(msg[4] or "") > 100 else f"📝 {msg[4]}\n"
        text += f"📅 {msg[10]}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

# ===== НАПИСАТЬ СООБЩЕНИЕ =====
@router.callback_query(F.data == "compose")
async def compose_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 <b>Кому отправить сообщение?</b>\n\n"
        "Введи ID пользователя или @username:\n"
        "Или попроси друга отправить тебе его ссылку",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ComposeStates.waiting_for_user)

@router.message(ComposeStates.waiting_for_user)
async def compose_get_user(message: Message, state: FSMContext):
    query = message.text.strip()
    users = await db.search_users(query)
    
    if not users:
        await message.answer(
            "❌ Пользователь не найден. Попробуй еще раз или нажми Отмена",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    user = users[0]
    if user[0] == message.from_user.id:
        await message.answer(
            "❌ Нельзя отправить сообщение самому себе!",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    name = f"@{user[1]}" if user[1] else user[2] or f"ID{user[0]}"
    
    await state.update_data(receiver_id=user[0], receiver_name=name)
    await message.answer(
        f"✅ Получатель: <b>{name}</b>\n\n"
        f"✍️ Теперь напиши сообщение (текст, фото или голосовое):\n"
        f"Для отмены нажми кнопку ниже",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ComposeStates.waiting_for_message)

@router.message(ComposeStates.waiting_for_message, F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def compose_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    receiver_id = data['receiver_id']
    receiver_name = data['receiver_name']
    
    try:
        if message.text:
            sent_msg = await bot.send_message(
                receiver_id,
                f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                parse_mode="HTML",
                reply_markup=get_message_keyboard(0)
            )
        elif message.photo:
            sent_msg = await bot.send_photo(
                receiver_id,
                message.photo[-1].file_id,
                caption="📨 <b>Анонимное фото</b>",
                parse_mode="HTML",
                reply_markup=get_message_keyboard(0)
            )
        elif message.voice:
            sent_msg = await bot.send_voice(
                receiver_id,
                message.voice.file_id,
                caption="📨 <b>Анонимное голосовое</b>",
                parse_mode="HTML",
                reply_markup=get_message_keyboard(0)
            )
        elif message.video_note:
            sent_msg = await bot.send_video_note(
                receiver_id,
                message.video_note.file_id,
                reply_markup=get_message_keyboard(0)
            )
        
        # Сохраняем в БД
        msg_id = await db.save_message(
            message.from_user.id,
            receiver_id,
            message.content_type,
            message.text or message.caption or "",
            sent_msg.message_id
        )
        
        # Обновляем клавиатуру с правильным ID
        await bot.edit_message_reply_markup(
            receiver_id,
            sent_msg.message_id,
            reply_markup=get_message_keyboard(sent_msg.message_id)
        )
        
        await message.answer(
            f"✅ Сообщение отправлено пользователю {receiver_name}!",
            reply_markup=get_main_menu(message.from_user.id, message.from_user.id == ADMIN_ID)
        )
        await db.add_log(ADMIN_ID, "message_sent", message.from_user.id, f"To: {receiver_id}")
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await message.answer(
            f"❌ Не удалось отправить сообщение. Возможно пользователь заблокировал бота.",
            reply_markup=get_main_menu(message.from_user.id, message.from_user.id == ADMIN_ID)
        )
    
    await state.clear()

@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if user_id in pending_messages:
        del pending_messages[user_id]
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )

# ===== ДЕЙСТВИЯ С СООБЩЕНИЯМИ =====
@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    try:
        receiver_message_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id
        
        msg = await db.get_message_by_receiver_id(receiver_message_id)
        if not msg:
            await callback.answer("❌ Сообщение не найдено", show_alert=True)
            return
        
        if msg[7]:  # уже раскрыто
            await callback.answer("⚠️ Отправитель уже раскрыт", show_alert=True)
            return
        
        # Проверяем стоимость
        if REVEAL_COST > 0 and not await db.is_premium(user_id):
            balance = await db.get_balance(user_id)
            if balance < REVEAL_COST:
                await callback.answer(f"❌ Недостаточно монет. Нужно {REVEAL_COST}", show_alert=True)
                return
            await db.add_balance(user_id, -REVEAL_COST, "Раскрытие отправителя")
        
        await db.reveal_message(msg[0])
        
        sender = await db.get_user(msg[1])
        if sender:
            name = f"@{sender[1]}" if sender[1] else sender[2] or f"ID{sender[0]}"
            await callback.answer(f"✅ Отправитель: {name}", show_alert=True)
            await db.add_log(ADMIN_ID, "reveal", user_id, f"Revealed sender {msg[1]}")
    except Exception as e:
        logger.error(f"Reveal error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("fav_"))
async def toggle_favorite(callback: CallbackQuery):
    try:
        receiver_message_id = int(callback.data.split("_")[1])
        msg = await db.get_message_by_receiver_id(receiver_message_id)
        if msg:
            is_fav = await db.toggle_favorite(msg[0])
            await callback.answer(
                "⭐ Добавлено в избранное" if is_fav else "Убрано из избранного",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Fav error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("delete_"))
async def delete_message(callback: CallbackQuery):
    try:
        receiver_message_id = int(callback.data.split("_")[1])
        msg = await db.get_message_by_receiver_id(receiver_message_id)
        if msg:
            await db.delete_message(msg[0])
            await callback.answer("🗑 Сообщение удалено", show_alert=True)
            await callback.message.delete()
    except Exception as e:
        logger.error(f"Delete error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("content_"))
async def show_content(callback: CallbackQuery):
    try:
        receiver_message_id = int(callback.data.split("_")[1])
        msg = await db.get_message_by_receiver_id(receiver_message_id)
        if msg and msg[4]:
            await callback.answer(f"📝 {msg[4][:200]}", show_alert=True)
        else:
            await callback.answer("📝 Это медиа-сообщение без текста", show_alert=True)
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

# ===== ОБРАБОТКА ПРЯМЫХ ССЫЛОК =====
@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    text = message.text.strip()
    
    # Проверяем не команда ли это /start с параметром
    if text.startswith("/start "):
        parts = text.split()
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
                if target_id != message.from_user.id:
                    # Начинаем процесс отправки
                    await state.set_state(ComposeStates.waiting_for_message)
                    await state.update_data(receiver_id=target_id, receiver_name=f"ID{target_id}")
                    await message.answer(
                        f"✍️ Напиши анонимное сообщение для пользователя ID{target_id}:",
                        reply_markup=get_cancel_keyboard()
                    )
                    return
            except:
                pass
    
    # Обычное сообщение - показываем меню
    if await state.get_state() is None:
        await message.answer(
            "👋 Используй меню ниже для навигации\n"
            "Или отправь /start для начала",
            reply_markup=get_main_menu(message.from_user.id, message.from_user.id == ADMIN_ID)
        )

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    text = (
        "❓ <b>Помощь по боту</b>\n\n"
        "<b>📨 Как получить сообщения:</b>\n"
        "1. Нажми '🔗 Моя ссылка'\n"
        "2. Скопируй ссылку\n"
        "3. Отправь друзьям\n"
        "4. Они смогут писать тебе анонимно\n\n"
        "<b>📝 Как написать сообщение:</b>\n"
        "1. Нажми '📝 Написать'\n"
        "2. Введи ID или @username получателя\n"
        "3. Или перейди по ссылке друга\n"
        "4. Отправь текст, фото или голосовое\n\n"
        "<b>👁 Как раскрыть отправителя:</b>\n"
        "1. Нажми '👁 Узнать отправителя'\n"
        "2. Premium - бесплатно\n"
        f"3. Или за {REVEAL_COST} монет\n\n"
        "<b>💰 Как заработать:</b>\n"
        f"1. Приглашай друзей (+{REFERRAL_BONUS} монет)\n"
        "2. Получай бонусы\n\n"
        "<b>💎 Premium:</b>\n"
        f"1. Купи за {PREMIUM_PRICE} монет\n"
        "2. Или активируй промокод\n\n"
        "<b>📞 Поддержка:</b>\n"
        "По вопросам обращайся к администратору"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
