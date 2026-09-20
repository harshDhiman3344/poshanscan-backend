import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime
from app.core.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    block = Column(String(100), nullable=False)
    village = Column(String(100), nullable=False, index=True)
    anganwadi_center = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
