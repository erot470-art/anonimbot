import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from config import BOT_TOKEN
from database import Database
from handlers import router
from admin_handlers import admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Health check для Render
async def health_check(request):
    return web.Response(text="OK")

async def run_web_server():
    """Запуск веб-сервера для проверки работоспособности"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    """Главная функция запуска бота"""
    try:
        # Проверяем и создаем директорию для БД если нужно
        from config import DATABASE_NAME
        import os
        db_dir = os.path.dirname(DATABASE_NAME)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created directory: {db_dir}")
        
        # Инициализация базы данных
        db = Database()
        await db.create_tables()
        logger.info("База данных инициализирована")
        
        # Инициализация бота
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher()
        
        # Подключаем роутеры
        dp.include_router(admin_router)
        dp.include_router(router)
        
        # Запускаем веб-сервер для Health Check
        asyncio.create_task(run_web_server())
        
        # Удаляем вебхук и запускаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот запущен!")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
