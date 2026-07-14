cat > handlers.py << 'EOF'
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from database import Database
from keyboards import get_start_keyboard, get_reveal_keyboard, get_back_keyboard
from utils import can_reveal_sender, get_user_display_name
from config import ADMIN_ID

router = Router()
db = Database()
user_states = {}


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Обработчик /start"""
    user_id = message.from_user.id
    
    # Регистрируем пользователя
    await db.register_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    args = message.text.split()
    
    # Если есть аргументы (переход по ссылке)
    if len(args) > 1:
        try:
            target_user_id = int(args[1])
            
            if target_user_id == user_id:
                await message.answer("❌ Нельзя отправлять сообщения самому себе!")
                return
            
            target_user = await db.get_user_info(target_user_id)
            if not target_user:
                await message.answer("❌ Пользователь не найден")
                return
            
            user_states[user_id] = target_user_id
            
            await message.answer(
                "✍️ Отправьте анонимное сообщение (текст, фото или голосовое)\n"
                "Для отмены: /cancel",
                reply_markup=get_back_keyboard()
            )
        except ValueError:
            await message.answer("❌ Некорректная ссылка")
    else:
        text = "👋 Добро пожаловать в Анонимный Чат!\n\n"
        text += "🔒 Получайте анонимные сообщения\n"
        text += "🔗 Поделитесь ссылкой с друзьями\n"
        text += "👁 Узнайте отправителя\n\n"
        text += "Выберите действие:"
        
        if user_id == ADMIN_ID:
            text += "\n\n⚙️ Админ-панель: /admin"
        
        await message.answer(text, reply_markup=get_start_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Отмена"""
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await message.answer("❌ Отправка отменена", reply_markup=get_start_keyboard())
    else:
        await message.answer("🤔 Нет активных действий")


@router.callback_query(F.data == "get_link")
async def get_user_link(callback: CallbackQuery):
    """Получить ссылку"""
    user_id = callback.from_user.id
    link = await create_start_link(callback.bot, str(user_id))
    
    await callback.message.edit_text(
        f"🔗 Ваша ссылка:\n\n<code>{link}</code>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """В меню"""
    user_id = callback.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    text = "👋 Добро пожаловать в Анонимный Чат!\n\nВыберите действие:"
    if user_id == ADMIN_ID:
        text += "\n\n⚙️ Админ-панель: /admin"
    
    await callback.message.edit_text(text, reply_markup=get_start_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    """Раскрыть отправителя"""
    user_id = callback.from_user.id
    message_id = int(callback.data.split("_")[1])
    
    if await db.is_already_revealed(message_id):
        await callback.answer("⚠️ Уже раскрыто", show_alert=True)
        return
    
    sender_id = await db.get_sender_id(message_id)
    if not sender_id:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return
    
    can_reveal, msg = await can_reveal_sender(user_id)
    if not can_reveal:
        await callback.answer(msg, show_alert=True)
        return
    
    sender_info = await db.get_user_info(sender_id)
    if not sender_info:
        await callback.answer("❌ Отправитель не найден", show_alert=True)
        return
    
    await db.mark_as_revealed(message_id)
    sender_name = get_user_display_name(sender_info)
    await callback.answer(f"✅ Отправитель: {sender_name}", show_alert=True)


@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_anonymous_message(message: Message, bot: Bot):
    """Обработка сообщений"""
    user_id = message.from_user.id
    
    if user_id in user_states:
        receiver_id = user_states[user_id]
        
        try:
            if message.text:
                sent_msg = await bot.send_message(
                    chat_id=receiver_id,
                    text=f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                    parse_mode="HTML",
                    reply_markup=get_reveal_keyboard(0)
                )
            elif message.photo:
                sent_msg = await bot.send_photo(
                    chat_id=receiver_id,
                    photo=message.photo[-1].file_id,
                    caption="📨 <b>Анонимное фото</b>",
                    parse_mode="HTML",
                    reply_markup=get_reveal_keyboard(0)
                )
            elif message.voice:
                sent_msg = await bot.send_voice(
                    chat_id=receiver_id,
                    voice=message.voice.file_id,
                    caption="📨 <b>Анонимное голосовое</b>",
                    parse_mode="HTML",
                    reply_markup=get_reveal_keyboard(0)
                )
            else:
                sent_msg = await bot.send_video_note(
                    chat_id=receiver_id,
                    video_note=message.video_note.file_id,
                    reply_markup=get_reveal_keyboard(0)
                )
            
            await db.save_message(
                sender_id=user_id,
                receiver_id=receiver_id,
                receiver_message_id=sent_msg.message_id,
                message_type=message.content_type
            )
            
            await bot.edit_message_reply_markup(
                chat_id=receiver_id,
                message_id=sent_msg.message_id,
                reply_markup=get_reveal_keyboard(sent_msg.message_id)
            )
            
        except TelegramForbiddenError:
            pass
        except Exception as e:
            print(f"Error: {e}")
        
        await message.answer("✅ Сообщение отправлено!", reply_markup=get_start_keyboard())
        del user_states[user_id]
    else:
        await message.answer(
            "🤔 Используйте /start для инструкций",
            reply_markup=get_start_keyboard()
        )
EOF
