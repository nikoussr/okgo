from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
'''
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from database.session import get_async_session
from database.models import User, Trip, FinancialOperation, UserRole
from schemas.user import UserResponse
from api.deps import get_current_admin
'''
router = APIRouter()

'''
@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
        role: Optional[UserRole] = None,
        is_verified: Optional[bool] = None,
        is_active: Optional[bool] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить список всех пользователей с фильтрами"""
    query = select(User)

    if role:
        query = query.where(User.role == role)

    if is_verified is not None:
        query = query.where(User.is_verified == is_verified)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.order_by(User.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить детальную информацию о пользователе"""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.profile))
    )
    user = result.unique().scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/verify", response_model=UserResponse)
async def verify_user(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Верифицировать водителя или агента"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.role not in [UserRole.DRIVER, UserRole.AGENT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only drivers and agents can be verified"
        )

    user.is_verified = True
    await db.commit()
    await db.refresh(user)

    # TODO: Отправить уведомление пользователю

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/block", response_model=UserResponse)
async def block_user(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Заблокировать пользователя"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block admin users"
        )

    user.is_active = False
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/unblock", response_model=UserResponse)
async def unblock_user(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Разблокировать пользователя"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = True
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/trips", response_model=list[dict])
async def get_all_trips(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить список всех поездок"""
    result = await db.execute(
        select(Trip)
        .options(joinedload(Trip.driver), joinedload(Trip.vehicle))
        .order_by(Trip.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    trips = result.unique().scalars().all()

    return [
        {
            "id": t.id,
            "driver_id": t.driver_id,
            "driver_name": f"{t.driver.first_name} {t.driver.last_name}",
            "from_address": t.from_address,
            "to_address": t.to_address,
            "departure_datetime": t.departure_datetime,
            "status": t.status.value,
            "total_seats": t.total_seats,
            "available_seats": t.available_seats,
            "price_per_seat": t.price_per_seat
        }
        for t in trips
    ]


@router.get("/bookings", response_model=list[dict])
async def get_all_bookings(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить список всех бронирований"""
    result = await db.execute(
        select(Booking)
        .options(
            joinedload(Booking.trip),
            joinedload(Booking.passenger)
        )
        .order_by(Booking.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    bookings = result.unique().scalars().all()

    return [
        {
            "id": b.id,
            "trip_id": b.trip_id,
            "passenger_id": b.passenger_id,
            "passenger_name": f"{b.passenger.first_name} {b.passenger.last_name}",
            "seats_booked": b.seats_booked,
            "status": b.status.value,
            "created_at": b.created_at
        }
        for b in bookings
    ]


@router.get("/financial/report")
async def get_financial_report(
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_async_session)
):
    """Получить финансовый отчет"""
    # Статистика по бронированиям
    bookings_stats = await db.execute(
        select(
            func.count(Booking.id).label("total_bookings"),
            func.sum(Booking.seats_booked).label("total_seats_booked")
        )
    )
    bookings_data = bookings_stats.one()

    # Статистика по поездкам
    trips_stats = await db.execute(
        select(
            func.count(Trip.id).label("total_trips"),
            func.avg(Trip.price_per_seat).label("avg_price")
        )
    )
    trips_data = trips_stats.one()

    # Статистика по финансовым операциям
    financial_stats = await db.execute(
        select(
            FinancialOperation.operation_type,
            func.sum(FinancialOperation.amount).label("total_amount"),
            func.count(FinancialOperation.id).label("count")
        )
        .group_by(FinancialOperation.operation_type)
    )
    financial_data = financial_stats.all()

    return {
        "bookings": {
            "total_bookings": bookings_data.total_bookings or 0,
            "total_seats_booked": bookings_data.total_seats_booked or 0
        },
        "trips": {
            "total_trips": trips_data.total_trips or 0,
            "average_price_per_seat": float(trips_data.avg_price) if trips_data.avg_price else 0.0
        },
        "financial_operations": [
            {
                "type": row.operation_type.value,
                "total_amount": row.total_amount,
                "count": row.count
            }
            for row in financial_data
        ]
    }

'''