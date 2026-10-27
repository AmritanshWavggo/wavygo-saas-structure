from fastapi import APIRouter

from app.modules.vehicles.router import router as vehicles_router

api_router = APIRouter()


@api_router.get("/health")
def api_health_check() -> dict[str, str]:
    return {"status": "ok", "scope": "api"}


api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])
