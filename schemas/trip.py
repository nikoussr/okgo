from datetime import datetime
from typing import Optional
from pydantic import Field, field_validator
from schemas.base import BaseSchema
from database.models import CarClass, TripType, TripStatus
from datetime import datetime, timezone
from schemas.user import UserResponse
from schemas.vehicle import VehicleResponse
import enum


class TripSearchRole(str, enum.Enum):
    CREATOR = "creator"  # Поездки, где пользователь создатель
    DRIVER = "driver"  # Поездки, где пользователь водитель
    ALL = "all"  # Все поездки, связанные с пользователем


# ========== Trip Schemas ==========
class TripBase(BaseSchema):
    from_address: str = Field(..., min_length=1, max_length=500) # ОБЯЗАТЕЛЬНО
    to_address: str = Field(..., min_length=1, max_length=500) # ОБЯЗАТЕЛЬНО
    departure_datetime: datetime # ОБЯЗАТЕЛЬНО
    total_seats: int = Field(..., gt=0) # ОБЯЗАТЕЛЬНО
    passenger_phone_number: Optional[str] = None
    trip_type: TripType = TripType.OWN # ОБЯЗАТЕЛЬНО
    is_delegation_active: bool = False
    car_class: Optional[CarClass] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)  # Общая цена за поездку
    delegation_commission: Optional[float] = 0


class TripCreate(TripBase):
    vehicle_id: Optional[int] = None

    @field_validator('departure_datetime')
    @classmethod
    def validate_future_date(cls, v):
        if v <= datetime.now(timezone.utc):
            raise ValueError('Departure datetime must be in the future')
        return v

class TripUpdate(BaseSchema):
    from_address: Optional[str] = Field(None, min_length=1, max_length=500)  # ОБЯЗАТЕЛЬНО
    to_address: Optional[str] = Field(None, min_length=1, max_length=500)  # ОБЯЗАТЕЛЬНО
    departure_datetime: Optional[datetime] = None  # ОБЯЗАТЕЛЬНО
    total_seats: Optional[int] = Field(None, gt=0)  # ОБЯЗАТЕЛЬНО
    passenger_phone_number: Optional[str] = None
    trip_type: Optional[TripType] = None  # ОБЯЗАТЕЛЬНО
    is_delegation_active: Optional[bool] = False
    car_class: Optional[CarClass] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)  # Общая цена за поездку
    delegation_commission: Optional[float] = 0
    vehicle_id: Optional[int] = None
    status: Optional[TripStatus] = None

    @field_validator('departure_datetime')
    @classmethod
    def validate_future_date(cls, v):
        if v <= datetime.now(timezone.utc):
            raise ValueError('Departure datetime must be in the future')
        return v

class TripResponse(TripBase):
    id: int
    creator_id: int
    driver_id: Optional[int]  # Может быть пустым для делегированных поездок
    vehicle_id: Optional[int]
    status: TripStatus
    channel_message_id: Optional[int] # Может быть пустым для собственных поездок
    created_at: datetime


class TripSearchParams(BaseSchema):
    role: TripSearchRole = TripSearchRole.ALL  # Роль пользователя в поиске
    trip_type: Optional[TripType] = None
    status: Optional[TripStatus] = None
    is_delegation_active: Optional[bool] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(300, ge=1, le=300)

class TripWithDriver(BaseSchema):
    id: int
    creator_id: int
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    from_address: str
    to_address: str
    passenger_phone_number: str
    departure_datetime: datetime
    price: Optional[float] = None
    total_seats: int
    car_class: Optional[CarClass] = None
    description: Optional[str] = None
    trip_type: TripType
    status: TripStatus
    delegation_commission: float
    is_delegation_active: bool
    created_at: datetime

    # Дополнительные поля с информацией о водителе
    driver: Optional[UserResponse] = None
    creator: Optional[UserResponse] = None
    vehicle: Optional[VehicleResponse] = None

# ========== Trip Request Schemas ==========
class TripRequestBase(BaseSchema):
    from_address: str = Field(..., min_length=1, max_length=500)
    to_address: str = Field(..., min_length=1, max_length=500)
    departure_datetime: datetime
    seats_required: int = Field(..., gt=1)
    car_class: Optional[CarClass] = Field(None)
    passenger_phone_number: Optional[str] = Field(..., min_length=1, max_length=20)
    additional_info: Optional[str] = Field(..., max_length=500)



class TripRequestCreate(TripRequestBase):
    @field_validator('departure_datetime')
    @classmethod
    def validate_future_date(cls, v):
        # Если v - offset-naive, делаем его offset-aware в UTC
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        # Сравниваем с текущим временем в UTC
        now = datetime.now(timezone.utc)

        if v <= now:
            raise ValueError('Departure datetime must be in the future')
        return v


class TripRequestUpdate(BaseSchema):
    from_address: Optional[str] = Field(None, min_length=1, max_length=500)
    to_address: Optional[str] = Field(None, min_length=1, max_length=500)
    departure_datetime: Optional[datetime] = None
    seats_required: Optional[int] = Field(None, gt=1)
    car_class: Optional[CarClass] = Field(None)
    passenger_phone_number: Optional[str] = Field(None, min_length=1, max_length=20)
    additional_info: Optional[str] = Field(None, max_length=500)


class TripRequestResponse(TripRequestBase):
    id: int
    passenger_id: int
    agent_id: Optional[int] = None
    created_at: datetime


class TripRequestWithPassenger(TripRequestResponse):
    passenger: "UserResponse"


# Импорты для forward references
from schemas.user import UserResponse
from schemas.vehicle import VehicleResponse

TripWithDriver.model_rebuild()
TripRequestWithPassenger.model_rebuild()