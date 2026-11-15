from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ChildCreate(BaseModel):
    name: str = Field(..., min_length=1)
    dob: str = Field(..., description="YYYY-MM-DD")
    gender: str = Field(default="O", pattern="^(M|F|O)$")
    guardian_name: Optional[str] = None
    village: Optional[str] = None


class ChildScanSummary(BaseModel):
    scan_id: str
    age_category: str
    status: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ChildResponse(BaseModel):
    id: str
    child_id: str
    name: str
    dob: str
    gender: str
    guardian_name: Optional[str] = None
    village: Optional[str] = None
    has_child_scan: bool = False
    has_adult_scan: bool = False
    scans: List[ChildScanSummary] = Field(default_factory=list)
    image_url: Optional[str] = None
    photo_url: Optional[str] = None
    latest_scan_id: Optional[str] = None
    muac_estimate_mm: Optional[float] = None
    risk_band: Optional[str] = None
    confidence_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ChildScanStatusResponse(BaseModel):
    child_id: str
    has_scanned: bool = False
    already_scanned: bool = False
    existing_scan_id: Optional[str] = None
    age_category: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    scans: List[ChildScanSummary] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
