from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
import database.session
from config import settings
from api.v1.router import api_router
from services.background_tasks import task_manager
import asyncio
from telegram_bot.core import bot, dp, CHANNEL_ID
from telegram_bot import handlers
from prometheus_fastapi_instrumentator import Instrumentator

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_telegram_bot():
    """Запуск Telegram бота"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        dp.include_router(handlers.router)
        logger.info("🤖 Telegram bot starting polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Telegram bot error: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("Starting AllTransfer API...")
    logger.info(f"API Version: 1.0.0")
    logger.info(f"Docs available at: http://localhost:8000/docs")

    # Создаем таблицы при старте
    await database.session.create_tables()

    # Запускаем фоновую задачу проверки подписок
    subscription_task = asyncio.create_task(task_manager.start_subscription_checker())
    task_manager.tasks.append(subscription_task)
    logger.info("✅ Фоновая задача проверки подписок запущена")

    # Запускаем Telegram бота в фоновой задаче
    bot_task = asyncio.create_task(run_telegram_bot())
    task_manager.tasks.append(bot_task)
    logger.info("🤖 Telegram bot started as background task")

    yield

    # Shutdown code
    logger.info("Shutting down AllTransfer API...")

    # Останавливаем все фоновые задачи
    await task_manager.stop_all_tasks()

    # Останавливаем бота
    logger.info("Stopping Telegram bot...")
    for task in task_manager.tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error stopping task: {e}")

    # Закрываем сессию бота
    await bot.session.close()


# Создание приложения с lifespan
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="API для Telegram Mini App - AllTransfer",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/api/health")
async def health():
    bot_status = "unknown"
    try:
        me = await bot.get_me()
        bot_status = "running" if me else "not_responding"
    except Exception as e:
        bot_status = f"error: {e}"

    return {
        "status": "ok",
        "version": "1.0.0",
        "telegram_bot": bot_status
    }


# Подключение роутеров API v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Метрики Prometheus — доступны на /metrics (только с localhost, nginx не проксирует)
Instrumentator().instrument(app).expose(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)