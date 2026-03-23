from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status

from database.models import Review, User
from schemas.review import ReviewCreate

'''
async def create_review(
        review_data: ReviewCreate,
        passenger: User,
        db: AsyncSession
) -> Review:
    """Создать отзыв о водителе"""
    # Получаем бронирование
    result = await db.execute(
        select(Booking)
        .where(Booking.id == review_data.booking_id)
        .options(joinedload(Booking.trip))
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )

    # Проверки
    if booking.passenger_id != passenger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review your own bookings"
        )

    if booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can only review completed trips"
        )

    # Проверяем что отзыв еще не оставлен
    existing_review = await db.execute(
        select(Review).where(Review.booking_id == booking.id)
    )
    if existing_review.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review already exists for this booking"
        )

    # Создаем отзыв
    review = Review(
        booking_id=booking.id,
        passenger_id=passenger.id,
        driver_id=booking.trip.driver_id,
        rating=review_data.rating,
        comment=review_data.comment
    )

    db.add(review)

    # Обновляем средний рейтинг водителя
    driver_id = booking.trip.driver_id
    avg_rating_result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.driver_id == driver_id)
    )
    avg_rating, count = avg_rating_result.one()

    driver_result = await db.execute(
        select(User).where(User.id == driver_id)
    )
    driver = driver_result.scalar_one()
    driver.rating_avg = float(avg_rating) if avg_rating else 0.0
    driver.rating_count = count + 1

    await db.commit()
    await db.refresh(review)

    return review


async def get_driver_reviews(
        driver_id: int,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50
) -> List[Review]:
    """Получить отзывы о водителе"""
    result = await db.execute(
        select(Review)
        .where(Review.driver_id == driver_id)
        .order_by(Review.created_at.desc())
        .offset(skip)
        .limit(limit)
        .options(joinedload(Review.passenger))
    )
    return list(result.unique().scalars().all())

'''