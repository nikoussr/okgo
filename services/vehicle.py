from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from database.models import Vehicle, User
from schemas.vehicle import VehicleCreate, VehicleUpdate


async def create_vehicle(
        vehicle_data: VehicleCreate,
        driver: User,
        db: AsyncSession
) -> Vehicle:
    """Создать автомобиль"""
    # Проверяем уникальность номера
    result = await db.execute(
        select(Vehicle).where(Vehicle.license_plate == vehicle_data.license_plate)
    )
    existing_vehicle = result.scalar_one_or_none()

    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle with this license plate already exists"
        )

    vehicle = Vehicle(
        driver_id=driver.id,
        brand=vehicle_data.brand,
        model=vehicle_data.model,
        year=vehicle_data.year,
        color=vehicle_data.color,
        license_plate=vehicle_data.license_plate,
        car_class=vehicle_data.car_class,
        is_active=True,
        additional_info=vehicle_data.additional_info
    )
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)

    return vehicle


async def get_driver_vehicles(driver: User, db: AsyncSession) -> List[Vehicle]:
    """Получить все автомобили водителя"""
    result = await db.execute(
        select(Vehicle)
        .where(Vehicle.driver_id == driver.id)
        .order_by(Vehicle.id)
    )
    return list(result.scalars().all())


async def get_vehicle_by_id(vehicle_id: int, db: AsyncSession) -> Optional[Vehicle]:
    """Получить автомобиль по ID"""
    result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id)
    )
    return result.scalar_one_or_none()


async def update_vehicle(
        vehicle_id: int,
        vehicle_data: VehicleUpdate,
        driver: User,
        db: AsyncSession
) -> Vehicle:
    """Обновить автомобиль"""
    vehicle = await get_vehicle_by_id(vehicle_id, db)

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    if vehicle.driver_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own vehicles"
        )

    # Проверяем уникальность номера если он меняется
    if vehicle_data.license_plate and vehicle_data.license_plate != vehicle.license_plate:
        result = await db.execute(
            select(Vehicle).where(Vehicle.license_plate == vehicle_data.license_plate)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vehicle with this license plate already exists"
            )

    # Обновляем поля
    update_data = vehicle_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)

    await db.commit()
    await db.refresh(vehicle)

    return vehicle


async def delete_vehicle(vehicle_id: int, driver: User, db: AsyncSession) -> None:
    """Удалить автомобиль"""
    vehicle = await get_vehicle_by_id(vehicle_id, db)

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    if vehicle.driver_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own vehicles"
        )

    # Деактивируем вместо удаления
    vehicle.is_active = False
    await db.commit()
