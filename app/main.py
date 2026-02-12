from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.background import background_worker
from app.config import settings
from app.database import init_db
from app.routers import (
    admin,
    auth,
    camera,
    disputes,
    dogs,
    drivers,
    notifications,
    payments,
    ratings,
    realtime,
    rides,
    saved_destinations,
    trusted_receivers,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for PawRide dog rideshare platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    if settings.enable_background_jobs:
        await background_worker.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if settings.enable_background_jobs:
        await background_worker.stop()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


app.include_router(auth.router)
app.include_router(dogs.router)
app.include_router(trusted_receivers.router)
app.include_router(saved_destinations.router)
app.include_router(rides.router)
app.include_router(drivers.router)
app.include_router(payments.router)
app.include_router(ratings.router)
app.include_router(camera.router)
app.include_router(admin.router)
app.include_router(disputes.router)
app.include_router(notifications.router)
app.include_router(realtime.router)
