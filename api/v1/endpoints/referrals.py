from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from core.security import create_access_token
from database.session import get_async_session
from database.models import User, Referral
from schemas.auth import TokenResponse
from schemas.referral import ReferralPublicCreate
from schemas.user import UserResponse
from services.referral import create_referral, get_user_referrer
from api.deps import get_current_user
from datetime import timedelta
from sqlalchemy import select


router = APIRouter()


@router.post("", response_model=TokenResponse)
async def create_referral_public(
        referral_data: ReferralPublicCreate,
        db: AsyncSession = Depends(get_async_session)
):
    """
    Публичный эндпоинт для ввода реферального кода.
    Возвращает JWT токен после успешного применения кода.
    """
    # Ищем пользователя по telegram_id
    result = await db.execute(
        select(User).where(User.telegram_id == referral_data.telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверяем, нет ли уже реферального кода у пользователя
    existing_referral = await db.execute(
        select(Referral).where(Referral.referral_id == user.id)
    )
    if existing_referral.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже использовали реферальный код"
        )

    # Создаем реферальную запись
    referral = await create_referral(referral_data.referral_code, user, db)

    # Создаем JWT токен
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=access_token_expires
    )

    # Явно обновляем пользователя
    await db.refresh(user, ['created_at', 'updated_at'])

    # Теперь безопасно обращаемся к атрибутам
    user_dict = {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
        "phone_number": user.phone_number,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "subscription_exp": user.subscription_exp,
        "sbp_bank": user.sbp_bank,
        "sbp_phone_number": user.sbp_phone_number,
        "organization": user.organization,
        "rating_avg": float(user.rating_avg or 0.0),
        "rating_count": user.rating_count or 0,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user_dict)  # Используем словарь
    )
@router.get("", status_code = status.HTTP_200_OK)
async def get_my_referrer(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Получает информацию о реферере текущего пользователя"""

    has_referrer = await get_user_referrer(user.id, db)

    if not has_referrer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вы не использовали реферальный код"
        )

    return {"has_referrer": True, "message": "Вы использовали реферальный код"}
