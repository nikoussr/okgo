from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_async_session
from database.models import User
from schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from api.deps import get_current_driver
from services.vehicle import (
    create_vehicle, get_driver_vehicles, get_vehicle_by_id,
    update_vehicle, delete_vehicle
)

router = APIRouter()


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_vehicle(
        vehicle_data: VehicleCreate,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Добавить новый автомобиль (только для водителей)"""
    vehicle = await create_vehicle(vehicle_data, driver, db)
    return VehicleResponse.model_validate(vehicle)


@router.get("", response_model=list[VehicleResponse])
async def get_my_vehicles(
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить список автомобилей текущего водителя"""
    vehicles = await get_driver_vehicles(driver, db)
    return [VehicleResponse.model_validate(v) for v in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle_details(
        vehicle_id: int,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить детали автомобиля"""
    vehicle = await get_vehicle_by_id(vehicle_id, db)

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    if vehicle.driver_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return VehicleResponse.model_validate(vehicle)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_existing_vehicle(
        vehicle_id: int,
        vehicle_data: VehicleUpdate,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Обновить информацию об автомобиле"""
    vehicle = await update_vehicle(vehicle_id, vehicle_data, driver, db)
    return VehicleResponse.model_validate(vehicle)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_vehicle(
        vehicle_id: int,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Удалить автомобиль"""
    await delete_vehicle(vehicle_id, driver, db)