from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ScanResultResponse(BaseModel):
    scan_id: str
    client_scan_id: Optional[str] = None
    child_id: str
    muac_estimate_mm: float
    risk_band: str  # NORMAL, MAM, SAM
    confidence_score: float
    created_at: str

    class Config:
        from_attributes = True


class SyncScanMetadata(BaseModel):
    client_scan_id: str
    child_id: str
    worker_id: str
    captured_at: Optional[str] = None
    reference_type: Optional[str] = "aruco"
    reference_size_mm: Optional[float] = 50.0


class SyncScanItemResponse(BaseModel):
    client_scan_id: Optional[str] = None
    scan_id: Optional[str] = None
    child_id: Optional[str] = None
    muac_estimate_mm: Optional[float] = None
    risk_band: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None
