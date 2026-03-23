from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, UserRole
from core.security import validate_telegram_webapp_data, create_access_token
from config import settings
import logging
from fastapi import HTTPException, status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def authenticate_telegram_user(init_data: str, db: AsyncSession) -> tuple[str, User]:
    """
    Аутентификация пользователя через Telegram WebApp.
    Создает нового пользователя если не существует.
    Возвращает JWT токен и объект User.
    """
    # Валидируем данные от Telegram
    telegram_data = validate_telegram_webapp_data(init_data, settings.TELEGRAM_BOT_TOKEN)

    # Ищем пользователя
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_data['telegram_id'])
    )
    user = result.scalar_one_or_none()

    # Создаем нового пользователя если не существует
    if not user:
        user = User(
            telegram_id=telegram_data['telegram_id'],
            username=telegram_data.get('username'),
            first_name=telegram_data.get('first_name'),
            last_name=telegram_data.get('last_name'),
            role=UserRole.DRIVER,
            is_verified=False,
        )
        db.add(user)
        await db.flush()
        await db.commit()
        await db.refresh(user)
    else:
        # Обновляем данные пользователя из Telegram
        user.username = telegram_data.get('username') or user.username
        await db.commit()
        await db.refresh(user)

    # Проверяем, есть ли у пользователя реферер
    from services.referral import get_user_referrer
    has_referrer = await get_user_referrer(user.id, db)

    # Выдаем токен ТОЛЬКО если есть реферер
    if has_referrer:
        # Создаем JWT токен
        access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value},
            secret_key=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
            expires_delta=access_token_expires
        )
        logger.info(f"ПОЛЬЗОВАТЕЛЬ: {user.username}")
        logger.info(f"ТОКЕН: {access_token}")

        return access_token, user
    else:
        # Если нет реферера - вызываем исключение
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Для входа в приложение необходимо ввести реферальный код",
                "code": "REFERRAL_CODE_REQUIRED",
                "user_id": user.id,
                "telegram_id": user.telegram_id
            }
        )