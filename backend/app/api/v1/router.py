from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.vehicles.router import router as vehicles_router
from app.modules.customers.router import router as customers_router
from app.modules.bookings.router import router as bookings_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(customers_router, prefix="/customers", tags=["customers"])
api_router.include_router(bookings_router, prefix="/bookings", tags=["bookings"])
