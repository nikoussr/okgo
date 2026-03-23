from typing import Optional
from pydantic import Field
from schemas.base import BaseSchema
from database.models import CarClass


class VehicleBase(BaseSchema):
    brand: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1900, le=2030)
    color: str = Field(..., min_length=1, max_length=50)
    license_plate: str = Field(..., min_length=1, max_length=20)
    additional_info: Optional[str] = Field(None, max_length=200)  # Изменено здесь
    car_class: CarClass


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseSchema):
    brand: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2030)
    color: Optional[str] = Field(None, min_length=1, max_length=50)
    license_plate: Optional[str] = Field(None, min_length=1, max_length=20)
    car_class: Optional[CarClass] = None
    additional_info: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class VehicleResponse(VehicleBase):
    id: int
    driver_id: int
    photo_url: Optional[str] = None
    is_active: bool