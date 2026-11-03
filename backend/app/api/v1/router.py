from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.core.responses import success
from app.modules.vehicles.router import router as vehicles_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])
