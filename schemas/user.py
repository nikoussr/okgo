from datetime import datetime
from typing import Optional
from pydantic import Field
from schemas.base import BaseSchema
from database.models import UserRole


# ========== User Schemas ==========
class UserBase(BaseSchema):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None


class UserUpdate(BaseSchema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    balance: Optional[float] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    subscription_exp: Optional[datetime] = None
    sbp_bank: Optional[str] = None
    sbp_phone_number: Optional[str] = None


class UserResponse(UserBase):
    id: int
    telegram_id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    subscription_exp: datetime | None
    sbp_bank: str | None
    sbp_phone_number: str | None
    rating_avg: float | None
    rating_count: int | None
    created_at: datetime
    updated_at: datetime