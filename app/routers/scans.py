from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.child import Child
from app.models.scan import Scan
from app.schemas.scan import ScanResultResponse
from app.services.storage import save_upload_file
from app.services.cv_client import run_cv_inference, CVInferenceError

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("", response_model=ScanResultResponse)
async def submit_scan(
    image: UploadFile = File(...),
    child_id: str = Form(...),
    worker_id: str = Form(...),
    client_scan_id: Optional[str] = Form(None),
    captured_at: Optional[str] = Form(None),
    reference_type: str = Form("aruco"),
    reference_size_mm: float = Form(50.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a single online scan.
    Receives image + metadata, forwards to Yash's CV service, saves to DB,
    and returns ScanResultResponse matching Navya's frontend contract.
    """
    # 1. Verify child exists
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child record not found.",
        )

    # 2. Read image content and save to storage
    image_bytes = await image.read()
    image_path = save_upload_file(image_bytes, image.filename or "scan.jpg")

    # 3. Forward to CV service
    try:
        cv_result = await run_cv_inference(
            image_bytes=image_bytes,
            filename=image.filename or "scan.jpg",
            reference_type=reference_type,
            reference_size_mm=reference_size_mm,
        )
    except CVInferenceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "message": exc.message},
        )

    # 4. Standardize risk band to uppercase ('NORMAL', 'MAM', 'SAM')
    raw_band = (cv_result.risk_band or "NORMAL").upper()
    if "NORM" in raw_band:
        normalized_band = "NORMAL"
    elif "MAM" in raw_band:
        normalized_band = "MAM"
    else:
        normalized_band = "SAM"

    # 5. Persist scan record
    scan_record = Scan(
        client_scan_id=client_scan_id,
        child_id=child_id,
        worker_id=current_user.id,
        image_path=image_path,
        muac_estimate_mm=cv_result.muac_estimate_mm,
        risk_band=normalized_band,
        confidence_score=cv_result.confidence_score,
        quality_flags=cv_result.quality_flags.model_dump() if cv_result.quality_flags else None,
        sync_status="synced",
        captured_at=captured_at,
    )
    db.add(scan_record)
    db.commit()
    db.refresh(scan_record)

    created_iso = scan_record.created_at.isoformat() if scan_record.created_at else datetime.now(timezone.utc).isoformat()

    return ScanResultResponse(
        scan_id=scan_record.id,
        client_scan_id=scan_record.client_scan_id,
        child_id=scan_record.child_id,
        muac_estimate_mm=scan_record.muac_estimate_mm,
        risk_band=scan_record.risk_band,
        confidence_score=scan_record.confidence_score,
        created_at=created_iso,
    )
