from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_async_session
from database.models import User, TripType, TripStatus
from schemas.trip import (
    TripCreate, TripUpdate, TripResponse, TripWithDriver,
    TripSearchParams, TripSearchRole

)
from api.deps import get_current_driver, get_current_user
from services.trip import (
    create_trip, get_trip_by_id,
    update_trip, delete_trip, search_my_trips_service
)


router = APIRouter()


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_new_trip(
        trip_data: TripCreate,
        driver: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Создать новую поездку (только для водителей)"""
    trip = await create_trip(trip_data, driver, db)
    return TripResponse.model_validate(trip)



@router.get("/search", response_model=list[TripWithDriver])
async def search_my_trips(
        role: TripSearchRole = TripSearchRole.ALL,  # Новый параметр!
        trip_type: Optional[str] = None,
        is_delegation_active: Optional[bool] = None,
        status: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(300, ge=1, le=300),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Поиск поездок текущего пользователя с фильтрами"""

    # Парсим enum параметры
    try:
        trip_type_enum = TripType(trip_type) if trip_type else None
        status_enum = TripStatus(status) if status else None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter value: {str(e)}"
        )

    # Создаем параметры поиска
    params = TripSearchParams(
        role=role,  # Передаем роль
        trip_type=trip_type_enum,
        is_delegation_active=is_delegation_active,
        status=status_enum,
        skip=skip,
        limit=limit
    )

    trips = await search_my_trips_service(params, current_user, db)
    return [TripWithDriver.model_validate(trip) for trip in trips]


@router.get("/{trip_id}", response_model=TripWithDriver)
async def get_trip_details(
        trip_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить детали поездки"""

    trip = await get_trip_by_id(trip_id, db)

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )

    return TripWithDriver.model_validate(trip)


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_existing_trip(
        trip_id: int,
        trip_data: TripUpdate,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Обновить поездку"""
    trip = await update_trip(trip_id, trip_data, driver, db)
    return TripResponse.model_validate(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_200_OK)
async def delete_existing_trip(
        trip_id: int,
        driver: User = Depends(get_current_driver),
        db: AsyncSession = Depends(get_async_session)
):
    """Удалить/отменить поездку"""
    result = await delete_trip(trip_id, driver, db)
    return result
