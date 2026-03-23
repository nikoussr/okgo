from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import HTTPException, status
from yookassa import Configuration, Payment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
import logging

# TODO: Спрятать ключи в секреты (цена за подписку, время на подписку)
# TODO: Почистить логи, оставить только саое важное. Убрать чувствительные данные


# Настройка логирования
logger = logging.getLogger(__name__)


async def check_all_subscriptions(db: AsyncSession) -> Dict[str, Any]:
    """
    Проверяет и обновляет статусы всех подписок
    Возвращает статистику
    """
    try:
        result = await db.execute(
            select(User).where(
                User.is_verified == True,
                User.subscription_exp.isnot(None)
            )
        )
        users_with_subscription = result.scalars().all()

        updated_count = 0
        active_count = 0

        # Получаем текущее время с timezone один раз
        current_time = datetime.now(timezone.utc)

        for user in users_with_subscription:
            # Сравниваем с timezone-aware datetime
            is_active_now = user.subscription_exp > current_time
            was_active = user.is_verified

            if was_active and not is_active_now:
                # Подписка истекла - деактивируем
                user.is_verified = False
                updated_count += 1
                logger.info(f"🔄 Подписка пользователя {user.id} истекла, деактивируем")
            elif is_active_now:
                active_count += 1

        # Коммитим изменения если есть что обновлять
        if updated_count > 0:
            await db.commit()
            logger.info(f"✅ Обновлено {updated_count} истекших подписок")

        logger.info(f"📊 Проверка подписок: {active_count} активных, {updated_count} истекших")

        return {
            "total_checked": len(users_with_subscription),
            "active_subscriptions": active_count,
            "expired_subscriptions": updated_count
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Ошибка при массовой проверке подписок: {str(e)}", exc_info=True)
        raise
