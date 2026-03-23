from fastapi import APIRouter, Depends, status, Query
'''
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_async_session
from database.models import User
from schemas.review import ReviewCreate, ReviewResponse, ReviewWithDetails
from api.deps import get_current_user
from services.review import create_review, get_driver_reviews
'''
router = APIRouter()

'''
@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_new_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Оставить отзыв о водителе (после завершения поездки)"""
    review = await create_review(review_data, current_user, db)
    return ReviewResponse.model_validate(review)


@router.get("/driver/{driver_id}", response_model=list[ReviewWithDetails])
async def get_reviews_for_driver(
    driver_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session)
):
    """Получить отзывы о водителе"""
    reviews = await get_driver_reviews(driver_id, db, skip, limit)
    return [ReviewWithDetails.model_validate(r) for r in reviews]
'''