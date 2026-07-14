from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link
from database import Database
from keyboards import *
from config import ADMIN_ID, REFERRAL_BONUS, REVEAL_COST
import random
import string

router = Router()
db = Database()
user_states = {}

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    referrer = None
    
    if len(args) > 1:
        try:
            referrer = int(args[1])
            if referrer == user_id:
                referrer = None
        except:
            pass
    
    await db.register_user(user_id, message.from_user.username, 
                          message.from_user.first_name, message.from_user.last_name, referrer)
    
    if referrer:
        await db.add_referral(referrer, user_id)
        await db.add_balance(referrer, REFERRAL_BONUS)
        try:
            await bot.send_message(referrer, f"🎉 Новый реферал! +{REFERRAL_BONUS} монет")
        except:
            pass
    
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\n"
        "🔒 Отправляй и получай анонимные сообщения\n"
        "👁 Раскрывай отправителей\n"
        "💰 Зарабатывай на рефералах\n"
        "💎 Premium статус\n\n"
        "Выбери действие:",
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=get_admin_keyboard(), parse_mode="HTML")
    else:
        await message.answer("🚫 Доступ запрещен")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        balance = user[4]
        is_premium = "✅ Да" if user[5] else "❌ Нет"
        referrals = await db.get_referral_count(message.from_user.id)
        await message.answer(
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 ID: {user[0]}\n"
            f"💰 Баланс: {balance} монет\n"
            f"💎 Premium: {is_premium}\n"
            f"👥 Рефералов: {referrals}",
            reply_markup=get_profile_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "my_link")
async def my_link(callback: CallbackQuery):
    link = await create_start_link(callback.bot, str(callback.from_user.id))
    await callback.message.edit_text(
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"💡 Приглашай друзей и получай {REFERRAL_BONUS} монет за каждого!",
        parse_mode="HTML", reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if user:
        balance = user[4]
        is_premium = "✅ Да" if user[5] else "❌ Нет"
        referrals = await db.get_referral_count(callback.from_user.id)
        await callback.message.edit_text(
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 ID: {user[0]}\n"
            f"💰 Баланс: {balance} монет\n"
            f"💎 Premium: {is_premium}\n"
            f"👥 Рефералов: {referrals}",
            reply_markup=get_profile_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "referrals")
async def referrals(callback: CallbackQuery):
    refs = await db.get_referrals(callback.from_user.id)
    count = len(refs)
    text = f"👥 <b>Рефералы ({count})</b>\n\n"
    if refs:
        for i, ref in enumerate(refs[:10], 1):
            name = f"@{ref[5]}" if ref[5] else ref[6]
            text += f"{i}. {name}\n"
    else:
        text += "У тебя пока нет рефералов"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data == "my_messages")
async def my_messages(callback: CallbackQuery):
    messages = await db.get_user_messages(callback.from_user.id, 10)
    if messages:
        text = "📨 <b>Последние сообщения:</b>\n\n"
        for msg in messages:
            sender = f"@{msg[8]}" if msg[8] else msg[9]
            text += f"От: {sender} | {'👁 Раскрыто' if msg[6] else '🔒 Анонимно'}\n"
    else:
        text = "У тебя пока нет сообщений"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())

@router.callback_query(F.data.startswith("reveal_"))
async def reveal(callback: CallbackQuery):
    msg_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    if await db.is_revealed(msg_id):
        await callback.answer("⚠️ Уже раскрыто", show_alert=True)
        return
    
    if REVEAL_COST > 0 and not await db.is_premium(user_id):
        balance = await db.get_balance(user_id)
        if balance < REVEAL_COST:
            await callback.answer(f"❌ Недостаточно монет. Нужно {REVEAL_COST}", show_alert=True)
            return
        await db.add_balance(user_id, -REVEAL_COST)
    
    sender_id = await db.get_sender(msg_id)
    if sender_id:
        user = await db.get_user(sender_id)
        name = f"@{user[1]}" if user[1] else user[2]
        await db.mark_revealed(msg_id)
        await callback.answer(f"✅ Отправитель: {name}", show_alert=True)

@router.callback_query(F.data.startswith("delete_"))
async def delete_msg(callback: CallbackQuery):
    await callback.answer("🗑 Сообщение удалено", show_alert=True)
    await callback.message.delete()

@router.callback_query(F.data == "back_to_menu")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        parse_mode="HTML", reply_markup=get_start_keyboard()
    )

@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_msg(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if user_id in user_states:
        receiver = user_states[user_id]
        content = message.text or message.caption or ""
        
        try:
            if message.text:
                msg = await bot.send_message(receiver, f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                    parse_mode="HTML", reply_markup=get_reveal_keyboard(0))
            elif message.photo:
                msg = await bot.send_photo(receiver, message.photo[-1].file_id,
                    caption="📨 <b>Анонимное фото</b>", parse_mode="HTML",
                    reply_markup=get_reveal_keyboard(0))
            elif message.voice:
                msg = await bot.send_voice(receiver, message.voice.file_id,
                    caption="📨 <b>Анонимное голосовое</b>", parse_mode="HTML",
                    reply_markup=get_reveal_keyboard(0))
            else:
                msg = await bot.send_video_note(receiver, message.video_note.file_id,
                    reply_markup=get_reveal_keyboard(0))
            
            await db.save_message(user_id, receiver, msg.message_id, message.content_type, content)
            await bot.edit_message_reply_markup(receiver, msg.message_id,
                reply_markup=get_reveal_keyboard(msg.message_id))
            await message.answer("✅ Сообщение отправлено!", reply_markup=get_start_keyboard())
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
        
        del user_states[user_id]
    else:
        text = message.text or ""
        if text.startswith("/start "):
            parts = text.split()
            if len(parts) > 1:
                try:
                    target = int(parts[1])
                    if target != user_id:
                        user_states[user_id] = target
                        await message.answer("✍️ Напиши анонимное сообщение:", reply_markup=get_back_keyboard())
                except:
                    pass
        else:
            await message.answer("👋 Используй /start чтобы начать")
