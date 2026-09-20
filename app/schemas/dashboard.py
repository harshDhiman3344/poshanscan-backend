from typing import List, Optional
from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_screenings: int
    normal_count: int
    mam_count: int
    sam_count: int
    average_confidence: float


class TrendItem(BaseModel):
    date: str
    total: int
    normal: int
    mam: int
    sam: int


class LocationAggregate(BaseModel):
    village: str
    total: int
    mam: int
    sam: int
    at_risk_count: int
    at_risk_percentage: float


class WorkerStats(BaseModel):
    worker_id: str
    worker_name: str
    phone: str
    total_screenings: int
    last_active: Optional[str] = None


class FlaggedScan(BaseModel):
    scan_id: str
    child_id: str
    child_name: str
    worker_id: str
    worker_name: str
    muac_estimate_mm: float
    risk_band: str
    confidence_score: float
    reason: str
    created_at: str
