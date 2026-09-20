import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), nullable=True)
    actor_id = Column(String(36), nullable=False)
    action = Column(String(100), nullable=False)
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
