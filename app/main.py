import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import (
    auth_router,
    children_router,
    scans_router,
    sync_router,
    dashboard_router,
    supervisor_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("poshanscan-backend")

FALLBACK_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010101004800480000ffdb004300030202020202030202020303030304060404040404080606050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc0000b080001000101011100ffda0008010100003f00d2cf20ffd9"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on application startup and apply migrations."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    # Apply database schema migrations & cleanup
    from app.core.migration import run_migrations
    run_migrations(engine)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Central API and integration layer for PoshanScan. "
        "Coordinates worker capture, CV inference microservice, "
        "relational storage, and supervisor analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware supporting local Vite development and remote deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for Render/uptime monitoring."""
    return {"status": "ok", "service": "poshanscan-backend"}


@app.get("/uploads/{filename}", tags=["Uploads"])
async def get_uploaded_image(filename: str):
    """Serve uploaded screening photo or graceful fallback if ephemeral disk restarted."""
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    default_img = os.path.join(settings.UPLOAD_DIR, "default_arm_scan.jpg")
    if os.path.exists(default_img):
        return FileResponse(default_img)
    return Response(content=FALLBACK_JPEG, media_type="image/jpeg")


os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# Include all functional routers
app.include_router(auth_router)
app.include_router(supervisor_router)
app.include_router(children_router)
app.include_router(scans_router)
app.include_router(sync_router)

# Supervisor Dashboard endpoints (primary prefix requested: /supervisor/dashboard)
app.include_router(dashboard_router, prefix="/supervisor/dashboard")
# Backward-compatible alias (legacy prefix: /dashboard)
app.include_router(dashboard_router, prefix="/dashboard")
