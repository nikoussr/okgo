from typing import Optional

from pydantic import Field
from schemas.base import BaseSchema
from schemas.user import UserResponse

class UserData(BaseSchema):
    id: str
    telegram_id: int
    username: str
    first_name: str
    last_name: str
    phone_number: str
    role: str
    is_active: bool
    is_verified: bool
    balance: float
    rating_avg: float
    rating_count: int

class TelegramAuthRequest(BaseSchema):
    init_data: str = Field(..., description="Telegram WebApp initData")


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse