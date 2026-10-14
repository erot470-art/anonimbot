from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import *
from utils import is_admin, is_super_admin, get_user_display_name
from config import REFERRAL_BONUS, REVEAL_COST, PREMIUM_PRICE, SUPER_ADMIN_ID
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# Хранилище активных отправок: {user_id: receiver_id}
active_sends = {}


class States(StatesGroup):
    waiting_for_code = State()


# ===================== /start =====================
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()

    # Регистрируем
    await db.register_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )

    if await db.is_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован.")
        return

    # Реферальная ссылка
    if len(args) > 1:
        param = args[1]

        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                if referrer_id != user_id:
                    await db.register_user(referrer_id, None, None, None)
                    ok, txt = await db.add_referral(referrer_id, user_id)
                    if ok:
                        await message.answer(f"🎉 Реферал засчитан!")
                        try:
                            await bot.send_message(referrer_id, f"🎉 Новый реферал! +{REFERRAL_BONUS} монет")
                        except:
                            pass
                    else:
                        await message.answer(f"ℹ️ {txt}")
                    return
            except Exception as e:
                logger.error(f"ref error: {e}")

        # Ссылка для сообщений (msg_ID)
        elif param.startswith("msg_"):
            try:
                target_id = int(param.replace("msg_", ""))
                if target_id == user_id:
                    await message.answer("❌ Нельзя отправить сообщение самому себе!")
                    return
                await db.register_user(target_id, None, None, None)
                active_sends[user_id] = target_id
                await message.answer(
                    "✍️ <b>Отправь анонимное сообщение</b>\n\n"
                    "• Текст\n• Фото\n• Голосовое\n• Видео-кружок\n\n"
                    "Для отмены: /cancel",
                    parse_mode="HTML"
                )
                return
            except Exception as e:
                logger.error(f"msg link error: {e}")

    # Главное меню
    admin = await is_admin(user_id)
    await message.answer(
        "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
        reply_markup=get_main_menu(user_id, admin),
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    admin = await is_admin(user_id)
    await message.answer("❌ Отменено", reply_markup=get_main_menu(user_id, admin))


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("🚫 Доступ запрещён")
        return
    super_admin = await is_super_admin(user_id)
    await message.answer("⚙️ <b>Админ-панель</b>",
        reply_markup=get_admin_menu(super_admin), parse_mode="HTML")


# ===================== ПРИЁМ СООБЩЕНИЙ =====================
@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_message(message: Message, bot: Bot):
    user_id = message.from_user.id

    if user_id in active_sends:
        receiver_id = active_sends[user_id]

        try:
            if message.text:
                sent = await bot.send_message(
                    receiver_id,
                    f"📨 <b>Анонимное сообщение:</b>\n\n{message.text}",
                    parse_mode="HTML"
                )
            elif message.photo:
                sent = await bot.send_photo(
                    receiver_id, message.photo[-1].file_id,
                    caption="📨 <b>Анонимное фото</b>", parse_mode="HTML"
                )
            elif message.voice:
                sent = await bot.send_voice(
                    receiver_id, message.voice.file_id,
                    caption="📨 <b>Анонимное голосовое</b>", parse_mode="HTML"
                )
            elif message.video_note:
                sent = await bot.send_video_note(
                    receiver_id, message.video_note.file_id
                )
            else:
                return

            await db.save_message(
                user_id, receiver_id,
                message.content_type,
                message.text or message.caption or "",
                sent.message_id
            )
            logger.info(f"Msg sent: {user_id} → {receiver_id}, msg_id={sent.message_id}")

            try:
                await bot.edit_message_reply_markup(
                    chat_id=receiver_id, message_id=sent.message_id,
                    reply_markup=get_message_keyboard(sent.message_id)
                )
            except Exception as e:
                logger.error(f"edit keyboard: {e}")

            admin = await is_admin(user_id)
            await message.answer(
                "✅ <b>Сообщение отправлено!</b>\n🔒 Твоя личность скрыта",
                parse_mode="HTML",
                reply_markup=get_main_menu(user_id, admin)
            )
        except Exception as e:
            logger.error(f"send error: {e}")
            admin = await is_admin(user_id)
            await message.answer(
                "❌ Не удалось отправить. Возможно, пользователь не начинал диалог с ботом.",
                reply_markup=get_main_menu(user_id, admin)
            )

        del active_sends[user_id]
        return

    # Иначе — показываем меню
    admin = await is_admin(user_id)
    await message.answer(
        "👋 Используй меню или перейди по ссылке друга",
        reply_markup=get_main_menu(user_id, admin)
    )


# ===================== МЕНЮ =====================
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await state.clear()
    admin = await is_admin(user_id)
    try:
        await callback.message.edit_text(
            "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id, admin)
        )
    except:
        await callback.message.answer(
            "🤖 <b>Анонимный Чат Бот</b>",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id, admin)
        )


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await state.clear()
    admin = await is_admin(user_id)
    await callback.message.edit_text("❌ Отменено", reply_markup=get_main_menu(user_id, admin))


@router.callback_query(F.data == "my_link")
async def my_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    u = bot_info.username
    msg_link = f"https://t.me/{u}?start=msg_{
