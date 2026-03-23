from sys import prefix

from fastapi import APIRouter

from api.v1.endpoints import auth, users, trips, vehicles, reviews, admin, payment, referrals

api_router = APIRouter()

# Подключаем все эндпоинты
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(trips.router, prefix="/trips", tags=["Trips"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["Vehicles"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
#api_router.include_router(payment.router, prefix="/payment", tags=["Payment"])
api_router.include_router(referrals.router, prefix='/referral', tags = ["Referral"])