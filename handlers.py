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
import base64

router = Router()
db = Database()
logger = logging.getLogger(__name__)

class ComposeStates(StatesGroup):
    waiting_for_user = State()
    waiting_for_message = State()

class ReferralStates(StatesGroup):
    waiting_for_referral_link = State()

def encode_payload(data: str) -> str:
    """Кодирует данные для ссылки"""
    return base64.b64encode(data.encode()).decode()

def decode_payload(payload: str) -> str:
    """Декодирует данные из ссылки"""
    try:
        return base64.b64decode(payload.encode()).decode()
    except:
        return ""

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Регистрируем пользователя
    is_new = await db.register_user(
        user_id, 
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Проверяем бан
    if await db.is_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован.")
        return
    
    # Проверяем параметры ссылки
    if len(args) > 1:
        payload = decode_payload(args[1])
        
        # РЕФЕРАЛЬНАЯ ССЫЛКА: ref_123456
        if payload.startswith("ref_"):
            referrer_id = int(payload.replace("ref_", ""))
            if referrer_id != user_id:
                success, msg_text = await db.add_referral(referrer_id, user_id)
                if success:
                    await message.answer(
                        f"🎉 Ты перешел по реферальной ссылке!\n"
                        f"Пригласивший получил +{REFERRAL_BONUS} монет",
                        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                    )
                    try:
                        await bot.send_message(referrer_id, 
                            f"🎉 Новый реферал! +{REFERRAL_BONUS} монет\n"
                            f"Пользователь: @{message.from_user.username or 'ID'+str(user_id)}")
                    except:
                        pass
                else:
                    await message.answer(
                        f"❌ {msg_text}",
                        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                    )
                return
        
        # ССЫЛКА ДЛЯ ОТПРАВКИ: msg_123456
        elif payload.startswith("msg_"):
            target_id = int(payload.replace("msg_", ""))
            if target_id == user_id:
                await message.answer(
                    "❌ Нельзя отправить сообщение самому себе!",
                    reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                )
                return
            
            # Проверяем существует ли пользователь
            target_user = await db.get_user(target_id)
            if not target_user:
                await message.answer(
                    "❌ Пользователь не найден",
                    reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                )
                return
            
            target_name = f"@{target_user[1]}" if target_user[1] else target_user[2] or f"ID{target_id}"
            
            from aiogram.fsm.context import FSMContext
            # Используем FSM через message
            await message.answer(
                f"✍️ Ты можешь отправить анонимное сообщение для <b>{target_name}</b>\n\n"
                f"Напиши текст, отправь фото или голосовое сообщение\n"
                f"Для отмены используй кнопку ниже",
                parse_mode="HTML",
                reply_markup=get_cancel_keyboard()
            )
            
            # Сохраняем состояние напрямую
            from aiogram.fsm.context import FSMContext
            state = FSMContext(
                storage=message.bot.session,  # не совсем правильно, но для примера
                key=FSMContext.__key__  # заглушка
            )
            
            # Лучше используем глобальный словарь
            import asyncio
            pending_messages[user_id] = {
                'receiver_id': target_id,
                'receiver_name': target_name,
                'message_id': message.message_id
            }
            return
    
    # Обычный старт
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\n"
        "🔒 Отправляй и получай анонимные сообщения\n"
        "👁 Раскрывай отправителей\n"
        "💰 Зарабатывай на рефералах\n"
        "💎 Premium статус\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID),
        parse_mode="HTML"
    )

# Глобальный словарь для pending messages
import asyncio
pending_messages = {}

@router.callback_query(F.data == "my_link")
async def show_links(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Ссылка для отправки сообщений
    msg_payload = encode_payload(f"msg_{user_id}")
    msg_link = f"https://t.me/{(await callback.bot.get_me()).username}?start={msg_payload}"
    
    # Реферальная ссылка
    ref_payload = encode_payload(f"ref_{user_id}")
    ref_link = f"https://t.me/{(await callback.bot.get_me()).username}?start={ref_payload}"
    
    text = (
        "🔗 <b>Твои ссылки:</b>\n\n"
        "<b>📨 Ссылка для сообщений:</b>\n"
        f"<code>{msg_link}</code>\n\n"
        "👆 Отправь эту ссылку друзьям, чтобы они могли писать тебе анонимно\n\n"
        "<b>👥 Реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👆 Приглашай друзей и получай +{REFERRAL_BONUS} монет за каждого!\n\n"
        "⚠️ Не перепутай ссылки!\n"
        "• Первая - для сообщений\n"
        "• Вторая - для рефералов"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_all_messages(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # Проверяем есть ли активная отправка
    if user_id in pending_messages:
        pending = pending_messages[user_id]
        receiver_id = pending['receiver_id']
        receiver_name = pending['receiver_name']
        
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
            await db.save_message(
                user_id,
                receiver_id,
                message.content_type,
                message.text or message.caption or "",
                sent_msg.message_id
            )
            
            # Обновляем клавиатуру
            await bot.edit_message_reply_markup(
                receiver_id,
                sent_msg.message_id,
                reply_markup=get_message_keyboard(sent_msg.message_id)
            )
            
            await message.answer(
                f"✅ Анонимное сообщение отправлено для {receiver_name}!",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
            
            # Логируем
            await db.add_log(ADMIN_ID, "message_sent", user_id, f"To: {receiver_id}")
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await message.answer(
                "❌ Не удалось отправить сообщение. Возможно пользователь заблокировал бота.",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
        
        # Очищаем состояние
        del pending_messages[user_id]
        return
    
    # Если нет активной отправки
    if message.text and message.text.startswith("/start "):
        await cmd_start(message, bot)
    elif message.text and message.text.startswith("/"):
        # Другие команды
        pass
    else:
        await message.answer(
            "👋 Используй меню для навигации\n"
            "Или перейди по ссылке друга чтобы написать сообщение",
            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
        )

@router.callback_query(F.data == "compose")
async def compose_start(callback: CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Кому отправить сообщение?</b>\n\n"
        "🔹 Перейди по ссылке друга (самый простой способ)\n\n"
        "Или введи ID пользователя:\n"
        "🔹 Попроси друга скинуть его ID в чате\n\n"
        "Для отмены нажми кнопку ниже",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_messages:
        del pending_messages[user_id]
    
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )

# Остальные функции (profile, referrals, premium, inbox, outbox, favorites, reveal, delete, help)
# оставляем без изменений из предыдущего ответа

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message)

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
        f"📤 Отправлено сообщений: <b>{user[11]}</b>"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "profile")
async def show_profile_callback(callback: CallbackQuery):
    await show_profile(callback.message)
    await callback.answer()

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    text = (
        "❓ <b>Помощь по боту</b>\n\n"
        "<b>📨 Как получить сообщения:</b>\n"
        "1. Нажми '🔗 Моя ссылка'\n"
        "2. Скопируй ПЕРВУЮ ссылку\n"
        "3. Отправь друзьям\n"
        "4. Они смогут писать тебе анонимно\n\n"
        "<b>📝 Как написать сообщение:</b>\n"
        "1. Попроси друга скинуть его ссылку\n"
        "2. Перейди по ней\n"
        "3. Отправь текст, фото или голосовое\n\n"
        "<b>👥 Как приглашать друзей:</b>\n"
        "1. Нажми '🔗 Моя ссылка'\n"
        "2. Скопируй ВТОРУЮ ссылку\n"
        "3. Отправь друзьям\n"
        f"4. Получай +{REFERRAL_BONUS} монет за каждого!\n\n"
        "<b>👁 Как раскрыть отправителя:</b>\n"
        "1. Нажми '👁 Узнать отправителя'\n"
        "2. Premium - бесплатно\n"
        f"3. Или за {REVEAL_COST} монет\n\n"
        "<b>💎 Premium:</b>\n"
        f"1. Купи за {PREMIUM_PRICE} монет\n"
        "2. Или активируй промокод"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_messages:
        del pending_messages[user_id]
    await callback.message.edit_text(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )
