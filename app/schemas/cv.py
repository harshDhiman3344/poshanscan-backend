from typing import Optional
from pydantic import BaseModel, Field


class CVQualityFlags(BaseModel):
    reference_detected: bool
    arm_detected: bool
    segmentation_ok: bool


class CVInferResponse(BaseModel):
    muac_estimate_mm: float
    risk_band: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    quality_flags: CVQualityFlags
    pipeline_version: str = "v1.0"
    age_category: Optional[str] = "child_6_59m"


class CVErrorResponse(BaseModel):
    error: str
    message: str
