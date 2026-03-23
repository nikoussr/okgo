from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_async_session
from database.models import User
from schemas.auth import TelegramAuthRequest, TokenResponse
from schemas.user import UserResponse
from services.auth import authenticate_telegram_user
from api.deps import get_current_user
router = APIRouter()


@router.post("/telegram", response_model=TokenResponse)
async def telegram_login(
        auth_data: TelegramAuthRequest,
        db: AsyncSession = Depends(get_async_session)
):
    """
    Аутентификация через Telegram WebApp.
    Создает нового пользователя если не существует.
    """
    access_token, user = await authenticate_telegram_user(auth_data.init_data, db)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return UserResponse.model_validate(current_user)