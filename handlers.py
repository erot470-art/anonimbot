from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from database import Database
from keyboards import *
from config import ADMIN_ID, REFERRAL_BONUS, REVEAL_COST, PREMIUM_PRICE
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# Хранилище активных отправок: {user_id: receiver_id}
active_sends = {}

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Регистрируем пользователя
    await db.register_user(
        user_id, 
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if await db.is_banned(user_id):
        await message.answer("⛔️ Вы заблокированы.")
        return
    
    # Если есть параметр в ссылке
    if len(args) > 1:
        param = args[1]
        
        # Реферальная ссылка
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                if referrer_id != user_id:
                    await db.register_user(referrer_id, None, None, None)
                    success, msg_text = await db.add_referral(referrer_id, user_id)
                    if success:
                        await message.answer(
                            f"🎉 Реферал! +{REFERRAL_BONUS} монет пригласившему",
                            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                        )
                        try:
                            await bot.send_message(referrer_id, f"🎉 Новый реферал! +{REFERRAL_BONUS}")
                        except:
                            pass
                        return
            except:
                pass
        
        # Ссылка для сообщений msg_123456
        elif param.startswith("msg_"):
            try:
                target_id = int(param.replace("msg_", ""))
                if target_id == user_id:
                    await message.answer("❌ Нельзя себе!")
                    return
                
                # Регистрируем получателя
                await db.register_user(target_id, None, None, None)
                
                # Активируем режим отправки
                active_sends[user_id] = target_id
                
                await message.answer(
                    "✍️ <b>Отправь анонимное сообщение:</b>\n\n"
                    "• Напиши текст\n"
                    "• Отправь фото\n"
                    "• Отправь голосовое\n\n"
                    "Для отмены: /cancel",
                    parse_mode="HTML"
                )
                return
            except Exception as e:
                logger.error(f"MSG link error: {e}")
        
        # Старая ссылка (только ID)
        else:
            try:
                target_id = int(param)
                if target_id != user_id:
                    await db.register_user(target_id, None, None, None)
                    active_sends[user_id] = target_id
                    await message.answer(
                        "✍️ Отправь анонимное сообщение:\n/cancel - отмена"
                    )
                    return
            except:
                pass
    
    # Главное меню
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID),
        parse_mode="HTML"
    )

@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
        await message.answer(
            "❌ Отправка отменена",
            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
        )

# ВАЖНО: Этот обработчик должен быть ПОСЛЕДНИМ для сообщений
@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # ПРОВЕРЯЕМ АКТИВНУЮ ОТПРАВКУ В ПЕРВУЮ ОЧЕРЕДЬ
    if user_id in active_sends:
        receiver_id = active_sends[user_id]
        
        # Отправляем сообщение
        try:
            if message.text:
                sent = await bot.send_message(
                    receiver_id,
                    f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                    parse_mode="HTML",
                    reply_markup=get_message_keyboard(0)
                )
            elif message.photo:
                sent = await bot.send_photo(
                    receiver_id,
                    message.photo[-1].file_id,
                    caption="📨 <b>Анонимное фото</b>",
                    parse_mode="HTML",
                    reply_markup=get_message_keyboard(0)
                )
            elif message.voice:
                sent = await bot.send_voice(
                    receiver_id,
                    message.voice.file_id,
                    caption="📨 <b>Анонимное голосовое</b>",
                    parse_mode="HTML",
                    reply_markup=get_message_keyboard(0)
                )
            elif message.video_note:
                sent = await bot.send_video_note(
                    receiver_id,
                    message.video_note.file_id,
                    reply_markup=get_message_keyboard(0)
                )
            else:
                return
            
            # Сохраняем в БД
            await db.save_message(
                user_id,
                receiver_id,
                message.content_type,
                message.text or message.caption or "",
                sent.message_id
            )
            
            # Обновляем клавиатуру
            try:
                await bot.edit_message_reply_markup(
                    receiver_id,
                    sent.message_id,
                    reply_markup=get_message_keyboard(sent.message_id)
                )
            except:
                pass
            
            # Уведомляем отправителя
            await message.answer(
                "✅ <b>Сообщение отправлено!</b>\n\n"
                "🔒 Твоя личность скрыта",
                parse_mode="HTML",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
            
        except Exception as e:
            logger.error(f"Send error: {e}")
            await message.answer(
                "❌ Ошибка отправки. Пользователь не начал диалог с ботом.",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
        
        # Очищаем состояние
        del active_sends[user_id]
        return
    
    # Если нет активной отправки - показываем меню
    await message.answer(
        "👋 Используй меню или перейди по ссылке друга:\n"
        "/start - главное меню",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )

# ===== КНОПКИ МЕНЮ =====
@router.callback_query(F.data == "my_link")
async def show_links(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    msg_link = f"https://t.me/{bot_username}?start=msg_{user_id}"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    text = (
        "🔗 <b>Твои ссылки:</b>\n\n"
        "<b>📨 Для сообщений:</b>\n"
        f"<code>{msg_link}</code>\n\n"
        "<b>👥 Реферальная:</b>\n"
        f"<code>{ref_link}</code>"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка")
        return
    
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 <code>{user[0]}</code>\n"
        f"💰 {user[4]} монет\n"
        f"💎 {'Premium' if user[5] else 'Обычный'}\n"
        f"👥 {await db.get_referral_count(callback.from_user.id)} рефералов\n"
        f"📨 {user[10]} получено\n"
        f"📤 {user[11]} отправлено"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    refs = await db.get_referrals(callback.from_user.id)
    count = len(refs)
    
    text = f"👥 <b>Рефералы: {count}</b>\n💰 +{count * REFERRAL_BONUS} монет\n\n"
    
    if refs:
        for i, ref in enumerate(refs[:10], 1):
            name = f"@{ref[5]}" if ref[5] else ref[6] or f"ID{ref[2]}"
            text += f"{i}. {name}\n"
    else:
        text += "Нет рефералов. Отправь реферальную ссылку!"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    is_prem = await db.is_premium(callback.from_user.id)
    balance = await db.get_balance(callback.from_user.id)
    
    text = f"💎 Premium: {'✅' if is_prem else '❌'}\n💰 Баланс: {balance}"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    success, msg = await db.buy_premium(callback.from_user.id)
    await callback.answer(msg, show_alert=True)

@router.callback_query(F.data == "inbox")
async def show_inbox(callback: CallbackQuery):
    msgs = await db.get_received_messages(callback.from_user.id, 10)
    
    if not msgs:
        text = "📨 Нет входящих"
    else:
        text = "📨 <b>Входящие:</b>\n\n"
        for msg in msgs:
            status = "👁" if msg[7] else "🔒"
            text += f"{status} {msg[10]}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "outbox")
async def show_outbox(callback: CallbackQuery):
    msgs = await db.get_sent_messages(callback.from_user.id, 10)
    
    if not msgs:
        text = "📤 Нет исходящих"
    else:
        text = "📤 <b>Исходящие:</b>\n\n"
        for msg in msgs:
            text += f"Кому: {msg[9] or 'ID'+str(msg[2])}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    try:
        msg_id = int(callback.data.split("_")[1])
        msg = await db.get_message_by_receiver_id(msg_id)
        
        if msg and not msg[7]:
            await db.reveal_message(msg[0])
            sender = await db.get_user(msg[1])
            if sender:
                name = f"@{sender[1]}" if sender[1] else sender[2] or f"ID{sender[0]}"
                await callback.answer(f"✅ {name}", show_alert=True)
        else:
            await callback.answer("Уже раскрыто", show_alert=True)
    except:
        await callback.answer("Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("delete_"))
async def delete_msg(callback: CallbackQuery):
    try:
        msg_id = int(callback.data.split("_")[1])
        msg = await db.get_message_by_receiver_id(msg_id)
        if msg:
            await db.delete_message(msg[0])
            await callback.message.delete()
    except:
        pass

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await callback.message.edit_text(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "📨 <b>Получить сообщения:</b>\n"
        "Нажми 'Моя ссылка' → отправь ПЕРВУЮ ссылку\n\n"
        "📝 <b>Отправить сообщение:</b>\n"
        "Перейди по ссылке друга → напиши\n\n"
        "👥 <b>Рефералы:</b>\n"
        "Отправь ВТОРУЮ ссылку"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "compose")
async def compose_message(callback: CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Как отправить:</b>\n\n"
        "Попроси друга скинуть ссылку из кнопки 'Моя ссылка'\n\n"
        "Или используй прямую ссылку:\n"
        "<code>https://t.me/бот?start=msg_ID</code>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
