from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.customers.router import router as customers_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(customers_router)


@api_router.get("/health")
def api_health_check() -> dict[str, str]:
    return {"status": "ok", "scope": "api"}
