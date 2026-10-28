from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.mongodb import create_mongo_client, get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mongo_client = create_mongo_client()
    app.state.mongo_client = mongo_client
    app.state.database = get_database(mongo_client) if mongo_client is not None else None
    try:
        yield
    finally:
        if mongo_client is not None:
            mongo_client.close()

from app.db.mongodb import ensure_vehicle_indexes

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Run one-time startup tasks (indexes, etc.)."""
    ensure_vehicle_indexes()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
