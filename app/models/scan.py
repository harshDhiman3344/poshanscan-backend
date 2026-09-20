import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON
from app.core.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_scan_id = Column(String(64), index=True, nullable=True)  # Idempotency key from client
    child_id = Column(String(36), ForeignKey("children.id"), nullable=False, index=True)
    worker_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    image_path = Column(String(255), nullable=True)
    muac_estimate_mm = Column(Float, nullable=False)
    risk_band = Column(String(20), nullable=False)  # NORMAL, MAM, SAM
    confidence_score = Column(Float, nullable=False)
    quality_flags = Column(JSON, nullable=True)
    sync_status = Column(String(20), default="synced")  # synced, pending, flagged
    captured_at = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
