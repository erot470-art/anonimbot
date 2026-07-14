from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from database import Database
from keyboards import get_start_keyboard, get_reveal_keyboard, get_back_keyboard
from utils import can_reveal_sender, get_user_display_name, escape_markdown
from config import ADMIN_ID

# Инициализация роутера и базы данных
router = Router()
db = Database()

# Словарь для временного хранения состояний
user_states = {}


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Проверка на бан
    if await db.is_user_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован администратором.")
        return
    
    args = message.text.split()
    
    # Регистрируем пользователя
    await db.register_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Если это админ, показываем админ-клавиатуру
    if user_id == ADMIN_ID and len(args) == 1:
        from keyboards import get_admin_main_keyboard
        await message.answer(
            "👋 Добро пожаловать, Администратор!\n\n"
            "🔒 Здесь вы можете получать анонимные сообщения\n"
            "🔗 Поделитесь своей ссылкой с друзьями\n"
            "👁 Вы можете узнать, кто отправил сообщение\n\n"
            "⚙️ <b>Админ-панель:</b> /admin\n\n"
            "Выберите действие:",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Если есть аргументы (переход по ссылке другого пользователя)
    if len(args) > 1:
        try:
            target_user_id = int(args[1])
            
            # Проверяем, не пытается ли пользователь отправить сообщение самому себе
            if target_user_id == user_id:
                await message.answer(
                    "❌ Нельзя отправлять анонимные сообщения самому себе!",
                    reply_markup=get_start_keyboard()
                )
                return
            
            # Проверяем, не забанен ли получатель
            if await db.is_user_banned(target_user_id):
                await message.answer(
                    "❌ Этот пользователь недоступен.",
                    reply_markup=get_start_keyboard()
                )
                return
            
            # Проверяем, существует ли пользователь в базе
            target_user = await db.get_user_info(target_user_id)
            if not target_user:
                await message.answer(
                    "❌ Пользователь не найден в системе.",
                    reply_markup=get_start_keyboard()
                )
                return
            
            # Сохраняем состояние: кому отправляем сообщение
            user_states[user_id] = target_user_id
            
            await message.answer(
                f"✍️ Вы можете отправить анонимное сообщение пользователю.\n\n"
                f"📝 Напишите текст, отправьте фото или голосовое сообщение.\n"
                f"Для отмены используйте /cancel",
                reply_markup=get_back_keyboard()
            )
        except ValueError:
            await message.answer(
                "❌ Некорректная ссылка.",
                reply_markup=get_start_keyboard()
            )
    else:
        # Обычный старт бота
        await message.answer(
            "👋 Добро пожаловать в Анонимный Чат!\n\n"
            "🔒 Здесь вы можете получать анонимные сообщения\n"
            "🔗 Поделитесь своей ссылкой с друзьями\n"
            "👁 Вы можете узнать, кто отправил сообщение\n\n"
            "Выберите действие:",
            reply_markup=get_start_keyboard()
        )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда для открытия админ-панели"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ У вас нет доступа к админ-панели.")
        return
    
    from keyboards import get_admin_main_keyboard
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Отмена отправки сообщения"""
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await message.answer(
            "❌ Отправка сообщения отменена.",
            reply_markup=get_start_keyboard()
        )
    else:
        await message.answer("🤔 У вас нет активных действий для отмены.")


@router.callback_query(F.data == "get_link")
async def get_user_link(callback: CallbackQuery):
    """Получение персональной ссылки"""
    user_id = callback.from_user.id
    link = await create_start_link(callback.bot, str(user_id))
    
    await callback.message.edit_text(
        f"🔗 Ваша персональная ссылка:\n\n"
        f"<code>{link}</code>\n\n"
        f"Поделитесь этой ссылкой с друзьями, чтобы они могли отправлять вам анонимные сообщения!",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    """Объяснение работы бота"""
    await callback.message.edit_text(
        "📖 <b>Как это работает:</b>\n\n"
        "1️⃣ Вы получаете свою уникальную ссылку\n"
        "2️⃣ Делитесь ей с друзьями или в соцсетях\n"
        "3️⃣ Люди отправляют вам анонимные сообщения\n"
        "4️⃣ Вы можете узнать, кто отправил сообщение, нажав кнопку под ним\n\n"
        "🔒 Ваша анонимность защищена до тех пор, пока получатель не решит раскрыть вашу личность",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    
    # Очищаем состояние, если было
    if user_id in user_states:
        del user_states[user_id]
    
    # Если админ, добавляем подсказку про админ-панель
    text = (
        "👋 Добро пожаловать в Анонимный Чат!\n\n"
        "🔒 Здесь вы можете получать анонимные сообщения\n"
        "🔗 Поделитесь своей ссылкой с друзьями\n"
        "👁 Вы можете узнать, кто отправил сообщение\n\n"
    )
    if user_id == ADMIN_ID:
        text += "⚙️ <b>Админ-панель:</b> /admin\n\n"
    text += "Выберите действие:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    """Раскрытие личности отправителя"""
    user_id = callback.from_user.id
    
    # Извлекаем ID сообщения
    message_id = int(callback.data.split("_")[1])
    
    # Проверяем, не было ли уже раскрыто
    if await db.is_already_revealed(message_id):
        await callback.answer("⚠️ Этот отправитель уже был раскрыт", show_alert=True)
        return
    
    # Получаем ID отправителя
    sender_id = await db.get_sender_id(message_id)
    
    if not sender_id:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return
    
    # Проверяем возможность раскрытия
    can_reveal, message = await can_reveal_sender(user_id)
    
    if not can_reveal:
        await callback.answer(message, show_alert=True)
        return
    
    # Получаем информацию об отправителе
    sender_info = await db.get_user_info(sender_id)
    
    if not sender_info:
        await callback.answer("❌ Отправитель не найден", show_alert=True)
        return
    
    # Отмечаем сообщение как раскрытое
    await db.mark_as_revealed(message_id)
    
    # Формируем имя отправителя
    sender_name = get_user_display_name(sender_info)
    
    await callback.answer(f"✅ Отправитель: {sender_name}", show_alert=True)


async def forward_anonymous_message(message: Message, bot: Bot, receiver_id: int):
    """Отправка анонимного сообщения получателю"""
    sender_id = message.from_user.id
    
    # Проверяем, не забанен ли получатель
    if await db.is_user_banned(receiver_id):
        return
    
    try:
        # Отправляем сообщение в зависимости от типа
        if message.text:
            sent_message = await bot.send_message(
                chat_id=receiver_id,
                text=f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                parse_mode="HTML",
                reply_markup=get_reveal_keyboard(0)
            )
        elif message.photo:
            sent_message = await bot.send_photo(
                chat_id=receiver_id,
                photo=message.photo[-1].file_id,
                caption=f"📨 <b>Анонимное фото</b>",
                parse_mode="HTML",
                reply_markup=get_reveal_keyboard(0)
            )
        elif message.voice:
            sent_message = await bot.send_voice(
                chat_id=receiver_id,
                voice=message.voice.file_id,
                caption=f"📨 <b>Анонимное голосовое сообщение</b>",
                parse_mode="HTML",
                reply_markup=get_reveal_keyboard(0)
            )
        elif message.video_note:
            sent_message = await bot.send_video_note(
                chat_id=receiver_id,
                video_note=message.video_note.file_id,
                reply_markup=get_reveal_keyboard(0)
            )
        else:
            # Другие типы сообщений
            sent_message = await bot.forward_message(
                chat_id=receiver_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            await bot.send_message(
                chat_id=receiver_id,
                text="📨 <b>Анонимное сообщение</b>",
                parse_mode="HTML",
                reply_markup=get_reveal_keyboard(sent_message.message_id)
            )
            return
        
        # Сохраняем информацию о сообщении в БД
        await db.save_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            receiver_message_id=sent_message.message_id,
            message_type=message.content_type
        )
        
        # Обновляем клавиатуру с правильным ID сообщения
        await bot.edit_message_reply_markup(
            chat_id=receiver_id,
            message_id=sent_message.message_id,
            reply_markup=get_reveal_keyboard(sent_message.message_id)
        )
        
    except TelegramForbiddenError:
        pass
    except TelegramAPIError as e:
        print(f"Ошибка при отправке сообщения: {e}")


@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_anonymous_message(message: Message, bot: Bot):
    """Обработка сообщений для отправки"""
    user_id = message.from_user.id
    
    # Проверка на бан
    if await db.is_user_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован администратором.")
        return
    
    # Проверяем, находится ли пользователь в режиме отправки
    if user_id in user_states:
        receiver_id = user_states[user_id]
        
        # Отправляем анонимное сообщение
        await forward_anonymous_message(message, bot, receiver_id)
        
        # Уведомляем отправителя
        await message.answer(
            "✅ Ваше анонимное сообщение успешно отправлено!",
            reply_markup=get_start_keyboard()
        )
        
        # Очищаем состояние
        del user_states[user_id]
    else:
        # Если пользователь не в режиме отправки, показываем меню
        text = "🤔 Чтобы отправить анонимное сообщение, перейдите по ссылке пользователя.\n\nИспользуйте /start для получения инструкций."
        if user_id == ADMIN_ID:
            text += "\n\n⚙️ <b>Админ-панель:</b> /admin"
        
        await message.answer(
            text,
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
