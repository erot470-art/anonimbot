from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import *
from config import ADMIN_ID, REFERRAL_BONUS, REVEAL_COST, PREMIUM_PRICE
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# {user_id: receiver_id}
active_sends = {}


class CodeStates(StatesGroup):
    waiting_code = State()


# ===================== /start =====================
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()

    await db.register_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )

    if await db.is_banned(user_id):
        await message.answer("⛔️ Ваш аккаунт заблокирован.")
        return

    if len(args) > 1:
        param = args[1]

        # Реферальная ссылка
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                if referrer_id != user_id:
                    await db.register_user(referrer_id, None, None, None)
                    ok, txt = await db.add_referral(referrer_id, user_id)
                    if ok:
                        await message.answer(
                            f"🎉 Ты перешёл по реферальной ссылке!",
                            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                        )
                        try:
                            await bot.send_message(referrer_id, f"🎉 Новый реферал! +{REFERRAL_BONUS} монет")
                        except:
                            pass
                    else:
                        await message.answer(
                            f"ℹ️ {txt}",
                            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
                        )
                    return
            except Exception as e:
                logger.error(f"ref error: {e}")

        # Ссылка для сообщений
        elif param.startswith("msg_"):
            try:
                target_id = int(param.replace("msg_", ""))
                if target_id == user_id:
                    await message.answer("❌ Нельзя отправить сообщение самому себе!")
                    return

                # Регистрируем получателя если его нет
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

        # Старый формат (просто ID)
        else:
            try:
                target_id = int(param)
                if target_id != user_id:
                    await db.register_user(target_id, None, None, None)
                    active_sends[user_id] = target_id
                    await message.answer("✍️ Отправь сообщение:\n/cancel — отмена")
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
    await message.answer("❌ Отменено", reply_markup=get_main_menu(user_id, user_id == ADMIN_ID))


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 Доступ запрещён")
        return
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=get_admin_menu(), parse_mode="HTML")


# ===================== ПРИЁМ СООБЩЕНИЙ =====================
@router.message(F.content_type.in_({"text", "photo", "voice", "video_note"}))
async def handle_message(message: Message, bot: Bot):
    user_id = message.from_user.id

    # ЕСЛИ активирован режим отправки
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
                    receiver_id,
                    message.photo[-1].file_id,
                    caption="📨 <b>Анонимное фото</b>",
                    parse_mode="HTML"
                )
            elif message.voice:
                sent = await bot.send_voice(
                    receiver_id,
                    message.voice.file_id,
                    caption="📨 <b>Анонимное голосовое</b>",
                    parse_mode="HTML"
                )
            elif message.video_note:
                sent = await bot.send_video_note(
                    receiver_id,
                    message.video_note.file_id
                )
            else:
                return

            # Сохраняем с реальным ID
            await db.save_message(
                user_id,
                receiver_id,
                message.content_type,
                message.text or message.caption or "",
                sent.message_id
            )
            logger.info(f"Saved msg: receiver_msg_id={sent.message_id}, from={user_id} to={receiver_id}")

            # Прикрепляем клавиатуру с правильным ID
            try:
                await bot.edit_message_reply_markup(
                    chat_id=receiver_id,
                    message_id=sent.message_id,
                    reply_markup=get_message_keyboard(sent.message_id)
                )
            except Exception as e:
                logger.error(f"edit keyboard: {e}")

            await message.answer(
                "✅ <b>Сообщение отправлено!</b>\n\n🔒 Твоя личность скрыта",
                parse_mode="HTML",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )

        except Exception as e:
            logger.error(f"send error: {e}")
            await message.answer(
                "❌ Не удалось отправить. Пользователь не начинал диалог с ботом.",
                reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
            )

        del active_sends[user_id]
        return

    # Если ничего не активно — просто показываем меню
    await message.answer(
        "👋 Используй меню или перейди по ссылке друга",
        reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
    )


# ===================== МЕНЮ =====================
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await state.clear()
    try:
        await callback.message.edit_text(
            "🤖 <b>Анонимный Чат Бот</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
        )
    except:
        await callback.message.answer(
            "🤖 <b>Анонимный Чат Бот</b>",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id, user_id == ADMIN_ID)
        )


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in active_sends:
        del active_sends[user_id]
    await state.clear()
    await callback.message.edit_text("❌ Отменено", reply_markup=get_main_menu(user_id, user_id == ADMIN_ID))


@router.callback_query(F.data == "my_link")
async def my_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    u = bot_info.username

    msg_link = f"https://t.me/{u}?start=msg_{user_id}"
    ref_link = f"https://t.me/{u}?start=ref_{user_id}"

    text = (
        "🔗 <b>Твои ссылки:</b>\n\n"
        "<b>📨 Для сообщений:</b>\n"
        f"<code>{msg_link}</code>\n\n"
        "👆 Отправь друзьям — они смогут писать тебе анонимно\n\n"
        "<b>👥 Реферальная:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👆 За каждого друга +{REFERRAL_BONUS} монет"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка")
        return

    ref_count = await db.get_referral_count(callback.from_user.id)
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 <code>{user[0]}</code>\n"
        f"👤 @{user[1] or 'нет'}\n"
        f"💰 <b>{user[4]}</b> монет\n"
        f"💎 Premium: {'✅' if user[5] else '❌'}\n"
        f"🚫 Бан: {'✅' if user[6] else '❌'}\n"
        f"👥 Рефералов: <b>{ref_count}</b>\n"
        f"📨 Получено: <b>{user[11]}</b>\n"
        f"📤 Отправлено: <b>{user[12]}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())


@router.callback_query(F.data == "transactions")
async def show_transactions(callback: CallbackQuery):
    txs = await db.get_transactions(callback.from_user.id, 15)
    text = "💰 <b>История операций:</b>\n\n"
    if txs:
        for tx in txs:
            emoji = "➕" if tx[3] == "credit" else "➖"
            text += f"{emoji} {tx[2]:+.0f} — {tx[4] or ''}\n"
    else:
        text += "Пусто"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())


@router.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    refs = await db.get_referrals(callback.from_user.id)
    count = len(refs)
    text = f"👥 <b>Рефералы: {count}</b>\n💰 +{count * REFERRAL_BONUS} монет\n\n"
    if refs:
        for i, ref in enumerate(refs[:15], 1):
            name = f"@{ref[5]}" if ref[5] else ref[6] or f"ID{ref[2]}"
            text += f"{i}. {name}\n"
    else:
        text += "Пока пусто. Отправь реферальную ссылку!"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())


@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    is_prem = await db.is_premium(callback.from_user.id)
    balance = await db.get_balance(callback.from_user.id)
    if is_prem:
        text = "💎 <b>Premium активен!</b>\n\n✅ Бесплатное раскрытие отправителей"
    else:
        text = (
            f"💎 <b>Premium</b>\n\n"
            f"Стоимость: <b>{PREMIUM_PRICE}</b> монет\n"
            f"Твой баланс: <b>{balance}</b> монет\n\n"
            "Преимущества:\n"
            "✅ Бесплатное раскрытие отправителей"
        )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_menu())


@router.callback_query(F.data == "buy_premium")
async
