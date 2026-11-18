from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import router as bookings_router
from app.modules.customers.router import router as customers_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.documents.router import router as documents_router
from app.modules.finance.router import router as finance_router
from app.modules.maintenance.router import router as maintenance_router
from app.modules.notifications.router import router as notifications_router
from app.modules.payments.router import router as payments_router
from app.modules.reports.router import router as reports_router
from app.modules.security.router import router as security_router
from app.modules.settings.router import router as settings_router
from app.modules.staff.router import router as staff_router
from app.modules.tenants.router import router as tenants_router
from app.modules.vehicles.router import router as vehicles_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(security_router)
api_router.include_router(settings_router)
api_router.include_router(customers_router)


@api_router.get("/health")
def api_health_check() -> dict[str, str]:
    return {"status": "ok", "scope": "api"}


api_router.include_router(vehicles_router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(bookings_router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(finance_router, prefix="/finance", tags=["Finance"])
api_router.include_router(maintenance_router, prefix="/maintenance", tags=["Maintenance"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_router.include_router(staff_router)
api_router.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
