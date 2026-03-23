from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.session import get_async_session
from database.models import User
from schemas.user import UserResponse, UserUpdate
from api.deps import get_current_user


router = APIRouter()


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
        user_data: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Обновить профиль текущего пользователя"""
    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)



@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
        user_id: int,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    """Получить публичную информацию о пользователе"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)