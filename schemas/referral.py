from pydantic import Field
from schemas.base import BaseSchema
from datetime import datetime

class ReferralPublicCreate(BaseSchema):
    telegram_id: int = Field(..., description="Telegram ID пользователя")
    referral_code: int = Field(..., description="Telegram ID реферера")

class ReferralData(BaseSchema):
    referrer_id: int = Field(...)
    referral_id: int = Field(...)

class ReferralResponse(ReferralData):
    id : int
    created_at: datetime