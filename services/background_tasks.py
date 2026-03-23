
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_async_session
from services.payment import check_all_subscriptions

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    def __init__(self):
        self.is_running = False
        self.tasks = []

    async def start_subscription_checker(self):
        '''Запускает фоновую задачу проверки подписок'''
        self.is_running = True
        logger.info("✅ Запуск фоновой задачи проверки подписок")

        while self.is_running:
            try:
                # Используем контекст сессии
                async for session in get_async_session():
                    try:
                        result = await check_all_subscriptions(session)

                        if result['expired_subscriptions'] > 0:
                            logger.info(f"🔄 Обновлено {result['expired_subscriptions']} истекших подписок")
                        else:
                            logger.info(f"✅ Проверка подписок завершена: {result['active_subscriptions']} активных")

                    except Exception as e:
                        logger.error(f"❌ Ошибка в фоновой задаче проверки подписок: {str(e)}", exc_info=True)

                    break  # Выходим из цикла сессий

            except Exception as e:
                logger.error(f"❌ Критическая ошибка в фоновой задаче: {str(e)}", exc_info=True)

            # Ждем 1 часов до следующей проверки
            await asyncio.sleep(60 * 60 * 1)  # каждые 1 час

    async def stop_all_tasks(self):
        '''Останавливает все фоновые задачи'''
        self.is_running = False
        for task in self.tasks:
            task.cancel()
        logger.info("Все фоновые задачи остановлены")


# Глобальный экземпляр менеджера задач
task_manager = BackgroundTaskManager()
