from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from database.models import User, Referral
from typing import Optional


async def create_referral(
        referral_code: int,  # Это должен быть telegram_id реферера
        user: User,  # Текущий пользователь (реферал)
        db: AsyncSession
) -> Referral:
    """Создаёт новую запись в referrals"""

    # Ищем пользователя по telegram_id (реферера)
    result = await db.execute(
        select(User)
        .where(User.telegram_id == referral_code)
    )
    referrer: User = result.scalar_one_or_none()

    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с referral code {referral_code} не найден"
        )

    # Проверяем, что пользователь не приглашает сам себя
    if referrer.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя использовать собственный реферальный код"
        )

    # Проверяем, нет ли уже такой реферальной связи
    existing_referral = await db.execute(
        select(Referral)
        .where(Referral.referral_id == user.id)
    )
    if existing_referral.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже использовали реферальный код"
        )

    referral = Referral(
        referrer_id=referrer.id,  # ID реферера, а не telegram_id
        referral_id=user.id,  # ID реферала
    )

    db.add(referral)
    if user.subscription_exp:
        user.subscription_exp += timedelta(days=7)
    else:
        user.subscription_exp = datetime.now(timezone.utc) + timedelta(days=7)

    if referrer.subscription_exp:
        referrer.subscription_exp += timedelta(days=7)
    else:
        referrer.subscription_exp = datetime.now(timezone.utc) + timedelta(days=7)

    user.is_verified = True
    referrer.is_verified = True

    await db.commit()
    await db.refresh(referral)

    return referral


async def get_user_referrer(
        user_id: int,
        db: AsyncSession
) -> bool:
    """Проверяет, является ли пользователь рефералом (вводил ли он реферальный код)"""
    result = await db.execute(
        select(Referral)
        .where(Referral.referral_id == user_id)
    )
    referral = result.scalar_one_or_none()

    return referral is not None
