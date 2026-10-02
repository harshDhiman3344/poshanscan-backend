from typing import List, Optional
from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_screenings: int
    normal_count: int
    mam_count: int
    sam_count: int
    avg_confidence: float
    average_confidence: Optional[float] = None
    screenings_today: int = 0
    active_workers: int = 1


class TrendItem(BaseModel):
    date: str
    total: int
    normal: int
    mam: int
    sam: int


class DashboardTrends(BaseModel):
    points: List[TrendItem]


class LocationAggregate(BaseModel):
    location_id: str = "L1"
    village: str
    block: str = "Rajouri Garden"
    district: str = "West Delhi"
    lat: float = 28.6500
    lng: float = 77.1200
    total_screenings: int
    normal: int
    mam: int
    sam: int
    prevalence_pct: float
    # Backward compatibility
    total: Optional[int] = None
    at_risk_count: Optional[int] = None
    at_risk_percentage: Optional[float] = None


class WorkerStats(BaseModel):
    worker_id: str
    name: str
    worker_name: Optional[str] = None
    phone: str
    village: str = "Rampur"
    total_screenings: int
    last_active_at: Optional[str] = None
    last_active: Optional[str] = None
    avg_confidence: float = 0.90
    flagged_count: int = 0


class FlaggedScan(BaseModel):
    screening_id: str
    scan_id: Optional[str] = None
    child_ref: str
    child_id: Optional[str] = None
    child_name: Optional[str] = None
    worker_id: Optional[str] = None
    worker_name: str
    muac_estimate_mm: float
    risk_band: str
    confidence: float
    confidence_score: Optional[float] = None
    reason: Optional[str] = None
    quality_flags: List[str] = []
    status: str = "pending"
    captured_at: str
    created_at: Optional[str] = None
