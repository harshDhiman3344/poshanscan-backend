import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import (
    auth_router,
    children_router,
    scans_router,
    sync_router,
    dashboard_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("poshanscan-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on application startup and auto-seed if empty."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    # Auto-seed if database has less than 50 scans (e.g. fresh deployment or needs enriched demo dataset)
    try:
        from app.models.scan import Scan
        from app.core.database import SessionLocal
        from seed import seed
        db = SessionLocal()
        try:
            scan_count = db.query(Scan).count()
            if scan_count < 50:
                logger.info(f"Database has only {scan_count} scans. Automatically seeding enriched multi-worker dataset...")
                seed()
                logger.info("Auto-seeding complete.")
            else:
                logger.info(f"Database already seeded with {scan_count} screenings.")
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Auto-seed check encountered an issue: {exc}")

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


# Include all functional routers
app.include_router(auth_router)
app.include_router(children_router)
app.include_router(scans_router)
app.include_router(sync_router)
app.include_router(dashboard_router)
