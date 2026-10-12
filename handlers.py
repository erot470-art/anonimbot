@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    try:
        receiver_message_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id
        
        logger.info(f"Reveal request: receiver_msg_id={receiver_message_id}, user={user_id}")
        
        # Ищем сообщение по ID в чате получателя
        msg = await db.get_message_by_receiver_id(receiver_message_id)
        
        if not msg:
            logger.warning(f"Message not found: {receiver_message_id}")
            await callback.answer("❌ Сообщение не найдено в базе", show_alert=True)
            return
        
        logger.info(f"Found message: {msg}")
        
        # Проверяем что это наш получатель
        if msg[2] != user_id:
            await callback.answer("❌ Это не ваше сообщение", show_alert=True)
            return
        
        # Проверяем уже раскрыто
        if msg[7]:
            sender = await db.get_user(msg[1])
            if sender:
                name = f"@{sender[1]}" if sender[1] else sender[2] or f"ID{sender[0]}"
                await callback.answer(f"👁 Отправитель: {name}", show_alert=True)
            return
        
        # Проверяем баланс/Premium
        is_prem = await db.is_premium(user_id)
        balance = await db.get_balance(user_id)
        
        if not is_prem and REVEAL_COST > 0:
            if balance < REVEAL_COST:
                await callback.answer(
                    f"❌ Нужно {REVEAL_COST} монет. У вас: {balance}",
                    show_alert=True
                )
                return
            await db.add_balance(user_id, -REVEAL_COST, "Раскрытие отправителя")
        
        # Раскрываем
        await db.reveal_message(msg[0])
        sender = await db.get_user(msg[1])
        
        if sender:
            name = f"@{sender[1]}" if sender[1] else sender[2] or f"ID{sender[0]}"
            clickable = f'<a href="tg://user?id={sender[0]}">{name}</a>'
            await callback.answer(f"👁 Отправитель: {name}", show_alert=True)
            # Дополнительно отправим сообщение с кликабельной ссылкой
            await callback.message.reply(
                f"👁 <b>Отправитель раскрыт:</b>\n{clickable}\n"
                f"🆔 ID: <code>{sender[0]}</code>",
                parse_mode="HTML"
            )
            
            await db.add_log(ADMIN_ID, "reveal", user_id, f"Revealed sender {msg[1]}")
        else:
            await callback.answer("❌ Отправитель не найден", show_alert=True)
    
    except Exception as e:
        logger.error(f"Reveal error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
