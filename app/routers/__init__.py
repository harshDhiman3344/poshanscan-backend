from app.routers.auth import router as auth_router
from app.routers.children import router as children_router
from app.routers.scans import router as scans_router
from app.routers.sync import router as sync_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "children_router",
    "scans_router",
    "sync_router",
    "dashboard_router",
]
