from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link
from database import Database
from keyboards import *
from config import ADMIN_ID, REFERRAL_BONUS, REVEAL_COST, PREMIUM_PRICE
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

active_sends = {}

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    
    # ВСЕГДА регистрируем текущего пользователя
    await db.register_user(
        user_id, 
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if await db.is_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован.")
        return
    
    # Если есть параметр в ссылке
    if len(args) > 1:
        param = args[1]
        
        # РЕФЕРАЛЬНАЯ ССЫЛКА
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                if referrer_id != user_id:
                    # Регистрируем реферера если его нет
                    await db.register_user(referrer_id, None, None, None)
                    
                    success, msg_text = await db.add_referral(referrer_id, user_id)
                    if success:
                        await message.answer(
                            f"🎉 Ты перешел по реферальной ссылке!\n"
                            f"Пригласивший получил +{REFERRAL_BONUS} монет",
                            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                        )
                        try:
                            await bot.send_message(referrer_id, 
                                f"🎉 Новый реферал! +{REFERRAL_BONUS} монет")
                        except:
                            pass
                        return
            except:
                pass
        
        # ССЫЛКА ДЛЯ ОТПРАВКИ СООБЩЕНИЯ
        elif param.startswith("msg_"):
            try:
                target_id = int(param.replace("msg_", ""))
                if target_id == user_id:
                    await message.answer("❌ Нельзя отправить сообщение самому себе!")
                    return
                
                # Регистрируем получателя если его нет (чтобы избежать "не найден")
                await db.register_user(target_id, None, None, None)
                
                target_name = f"ID{target_id}"
                target_user = await db.get_user(target_id)
                if target_user:
                    target_name = f"@{target_user[1]}" if target_user[1] else target_user[2] or f"ID{target_id}"
                
                active_sends[user_id] = {
                    'receiver_id': target_id,
                    'receiver_name': target_name
                }
                
                await message.answer(
                    f"✍️ <b>Отправка анонимного сообщения</b>\n\n"
                    f"👤 Получатель: {target_name}\n\n"
                    f"Отправь текст, фото или голосовое:",
                    parse_mode="HTML",
                    reply_markup=get_cancel_keyboard()
                )
                return
            except Exception as e:
                logger.error(f"MSG link error: {e}")
        
        # СТАРАЯ ССЫЛКА (просто ID)
        else:
            try:
                target_id = int(param)
                if target_id != user_id:
                    await db.register_user(target_id, None, None, None)
                    
                    target_name = f"ID{target_id}"
                    target_user = await db.get_user(target_id)
                    if target_user:
                        target_name = f"@{target_user[1]}" if target_user[1] else target_user[2] or f"ID{target_id}"
                    
                    active_sends[user_id] = {
                        'receiver_id': target_id,
                        'receiver_name': target_name
                    }
                    
                    await message.answer(
                        f"✍️ Отправь анонимное сообщение для {target_name}:",
                        reply_markup=get_cancel_keyboard()
                    )
                    return
            except:
                pass
    
    # Главное меню
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\n"
        "🔒 Отправляй и получай анонимные сообщения\n"
        "👁 Раскрывай отправителей\n"
        "💰 Зарабатывай на рефералах\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID),
        parse_mode="HTML"
    )

@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await message.answer("❌ Отправка отменена", reply_markup=get_main_menu(user_id, user_id == ADMIN_ID))

@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_all_messages(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # Если есть активная отправка
    if user_id in active_sends:
        send_data = active_sends[user_id]
        receiver_id = send_data['receiver_id']
        receiver_name = send_data['receiver_name']
        
        try:
            if message.text:
                sent_msg = await bot.send_message(
                    receiver_id,
                    f"📨 <b>У вас анонимное сообщение!</b>\n\n{message.text}",
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
            else:
                await message.answer("❌ Неподдерживаемый тип сообщения")
                return
            
            await db.save_message(
                user_id,
                receiver_id,
                message.content_type,
                message.text or message.caption or "",
                sent_msg.message_id
            )
            
            try:
                await bot.edit_message_reply_markup(
                    receiver_id,
                    sent_msg.message_id,
                    reply_markup=get_message_keyboard(sent_msg.message_id)
                )
            except:
                pass
            
            await message.answer(
                f"✅ Сообщение отправлено пользователю {receiver_name}!",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
            
        except Exception as e:
            logger.error(f"Send error: {e}")
            await message.answer(
                "❌ Не удалось отправить. Возможно пользователь не начал диалог с ботом.",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )
        
        del active_sends[user_id]
        return
    
    # Без активной отправки
    if not message.text or not message.text.startswith("/"):
        await message.answer(
            "👋 Используй меню или перейди по ссылке друга",
            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
        )

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
        "👆 Отправь друзьям для анонимных сообщений\n\n"
        "<b>👥 Реферальная:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👆 Приглашай друзей (+{REFERRAL_BONUS} монет)"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "compose")
async def compose_message(callback: CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Как отправить сообщение:</b>\n\n"
        "1. Попроси друга нажать 'Моя ссылка'\n"
        "2. Попроси скинуть ПЕРВУЮ ссылку\n"
        "3. Перейди по ней\n"
        "4. Напиши сообщение\n\n"
        "Или используй прямую ссылку:\n"
        "<code>https://t.me/бот?start=ID</code>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка")
        return
    
    balance = user[4]
    is_premium = "💎 Да" if user[5] else "❌ Нет"
    ref_count = await db.get_referral_count(callback.from_user.id)
    
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"💰 Баланс: <b>{balance}</b> монет\n"
        f"💎 Premium: {is_premium}\n"
        f"👥 Рефералов: {ref_count}\n"
        f"📨 Получено: {user[10]}\n"
        f"📤 Отправлено: {user[11]}"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    refs = await db.get_referrals(callback.from_user.id)
    count = len(refs)
    
    text = f"👥 <b>Рефералы ({count})</b>\n💰 Заработано: {count * REFERRAL_BONUS} монет\n\n"
    
    if refs:
        for i, ref in enumerate(refs[:15], 1):
            name = f"@{ref[5]}" if ref[5] else ref[6] or f"ID{ref[2]}"
            text += f"{i}. {name}\n"
    else:
        text += "Поделись реферальной ссылкой!"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    is_prem = await db.is_premium(callback.from_user.id)
    balance = await db.get_balance(callback.from_user.id)
    
    if is_prem:
        text = "💎 <b>Premium активен!</b>"
    else:
        text = f"💎 Premium: {PREMIUM_PRICE} монет\n💰 Баланс: {balance} монет"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())

@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    success, msg = await db.buy_premium(callback.from_user.id)
    await callback.answer(msg, show_alert=True)

@router.callback_query(F.data == "inbox")
async def show_inbox(callback: CallbackQuery):
    msgs = await db.get_received_messages(callback.from_user.id, 10)
    
    if not msgs:
        text = "📨 Нет входящих сообщений"
    else:
        text = "📨 <b>Входящие:</b>\n\n"
        for msg in msgs:
            status = "👁" if msg[7] else "🔒"
            text += f"{status} Сообщение от {msg[10]}\n"
    
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
        
        if not msg:
            await callback.answer("Сообщение не найдено", show_alert=True)
            return
        
        if msg[7]:
            await callback.answer("Уже раскрыто", show_alert=True)
            return
        
        await db.reveal_message(msg[0])
        sender = await db.get_user(msg[1])
        
        if sender:
            name = f"@{sender[1]}" if sender[1] else sender[2] or f"ID{sender[0]}"
            await callback.answer(f"Отправитель: {name}", show_alert=True)
    except Exception as e:
        logger.error(f"Reveal error: {e}")
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
        "Нажми 'Моя ссылка' → отправь первую ссылку\n\n"
        "📝 <b>Отправить сообщение:</b>\n"
        "Перейди по ссылке друга → напиши сообщение\n\n"
        "👥 <b>Рефералы:</b>\n"
        "Отправь вторую ссылку друзьям"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await callback.message.edit_text("❌ Отменено", reply_markup=get_main_menu(user_id, user_id == ADMIN_ID))
