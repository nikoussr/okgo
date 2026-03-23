from datetime import datetime
from typing import Optional
from pydantic import Field
from schemas.base import BaseSchema


class ReviewBase(BaseSchema):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewCreate(ReviewBase):
    booking_id: int


class ReviewResponse(ReviewBase):
    id: int
    booking_id: int
    passenger_id: int
    driver_id: int
    created_at: datetime


class ReviewWithDetails(ReviewResponse):
    passenger: "UserResponse"


# Импорты для forward references
from schemas.user import UserResponse

ReviewWithDetails.model_rebuild()