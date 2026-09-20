import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.database import Base


class Child(Base):
    __tablename__ = "children"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, index=True)
    dob = Column(String(10), nullable=False)  # YYYY-MM-DD
    gender = Column(String(10), default="O")  # M, F, O
    guardian_name = Column(String(100), nullable=True, index=True)
    village = Column(String(100), nullable=True, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True)
    registered_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
