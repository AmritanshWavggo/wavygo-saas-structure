from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.mongodb import create_mongo_client, ensure_vehicle_indexes, get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mongo_client = create_mongo_client()
    app.state.mongo_client = mongo_client
    database = get_database(mongo_client) if mongo_client is not None else None
    app.state.database = database
    try:
        ensure_vehicle_indexes()
    except Exception:
        pass
    if database is not None:
        try:
            demo_bookings = ["BK-5001", "BK-5002", "BK-5003", "BK-5004", "BK-3984", "BK-3983", "BK-3982", "BK-3981", "BK-3980", "BK-3979", "BK-3985", "BK-3986", "BK-3987"]
            demo_payments = ["TX-8001", "TX-8002", "TX-8003", "TX-8004", "TX-7082", "TX-7081", "TX-7080", "TX-7079", "TX-7078"]
            demo_maintenance = ["MT-301", "MT-302", "MT-303", "MT-081", "MT-080", "MT-079", "MT-078"]
            demo_docs = ["DC-301", "DC-302", "DC-303", "DC-304", "DC-305", "DC-201", "DC-202", "DC-203", "DC-204", "DC-205", "DC-104", "DC-103", "DC-102", "DC-101", "DC-100"]
            database["bookings"].delete_many({"id": {"$in": demo_bookings}})
            database["payments"].delete_many({"id": {"$in": demo_payments}})
            database["maintenance"].delete_many({"id": {"$in": demo_maintenance}})
            database["documents"].delete_many({"id": {"$in": demo_docs}})
        except Exception:
            pass
    try:
        yield
    finally:
        if mongo_client is not None:
            mongo_client.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
# Also mount at root so requests without /api/v1 prefix work seamlessly
app.include_router(api_router)
