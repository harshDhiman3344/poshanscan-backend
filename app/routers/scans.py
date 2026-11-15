from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

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
    age_category: str = Form("child_6_59m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a single online scan.
    Receives image + metadata + age_category, forwards to Yash's CV service, saves to DB,
    and returns ScanResultResponse matching Navya's frontend contract.
    """
    # 1. Verify child exists
    # If child_id is explicitly "undefined", "null", or empty (frontend unselected param), fallback to the latest registered child.
    child = None
    clean_child_id = str(child_id).strip() if child_id else ""
    is_unspecified = not clean_child_id or clean_child_id.lower() in ("undefined", "null", "none")

    if not is_unspecified:
        child = db.query(Child).filter(
            (Child.id == clean_child_id) | (Child.name.ilike(clean_child_id))
        ).first()
    else:
        child = db.query(Child).order_by(Child.created_at.desc()).first()

    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child record not found.",
        )

    # Normalize age category: "adult" or "child_6_59m"
    norm_age = "adult" if str(age_category).strip().lower() == "adult" else "child_6_59m"

    # 1.1 Idempotency check: if exact client_scan_id already exists, return existing record
    if client_scan_id:
        existing_client_scan = db.query(Scan).filter(Scan.client_scan_id == client_scan_id).first()
        if existing_client_scan:
            created_iso = (
                existing_client_scan.created_at.isoformat()
                if existing_client_scan.created_at
                else datetime.now(timezone.utc).isoformat()
            )
            return ScanResultResponse(
                id=existing_client_scan.id,
                scan_id=existing_client_scan.id,
                client_scan_id=existing_client_scan.client_scan_id,
                child_id=existing_client_scan.child_id,
                age_category=existing_client_scan.age_category or "child_6_59m",
                muac_estimate_mm=existing_client_scan.muac_estimate_mm,
                risk_band=existing_client_scan.risk_band,
                confidence_score=existing_client_scan.confidence_score,
                created_at=created_iso,
            )

    # 1.2 Enforce at most one submitted scan photo per person and age category
    existing_scan = db.query(Scan).filter(
        Scan.child_id == child.id,
        Scan.age_category == norm_age,
    ).first()
    if existing_scan:
        created_iso = (
            existing_scan.created_at.isoformat()
            if existing_scan.created_at
            else datetime.now(timezone.utc).isoformat()
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "scan_already_exists",
                "detail": "scan_already_exists",
                "message": f"A scan for this person and age category ({norm_age}) already exists.",
                "scan_id": existing_scan.id,
                "child_id": existing_scan.child_id,
                "age_category": existing_scan.age_category,
                "status": existing_scan.sync_status,
                "created_at": created_iso,
            },
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
            age_category=norm_age,
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

    # 5. Persist scan record atomically
    scan_record = Scan(
        client_scan_id=client_scan_id,
        child_id=child.id,
        worker_id=current_user.id,
        image_path=image_path,
        age_category=norm_age,
        muac_estimate_mm=cv_result.muac_estimate_mm,
        risk_band=normalized_band,
        confidence_score=cv_result.confidence_score,
        quality_flags=cv_result.quality_flags.model_dump() if cv_result.quality_flags else None,
        sync_status="synced",
        captured_at=captured_at,
    )
    try:
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)
    except IntegrityError:
        db.rollback()
        # Atomic conflict resolution if a concurrent submission committed first
        conflict_scan = db.query(Scan).filter(
            Scan.child_id == child.id,
            Scan.age_category == norm_age,
        ).first()
        created_iso = (
            conflict_scan.created_at.isoformat()
            if conflict_scan and conflict_scan.created_at
            else datetime.now(timezone.utc).isoformat()
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "scan_already_exists",
                "detail": "scan_already_exists",
                "message": f"A scan for this person and age category ({norm_age}) already exists.",
                "scan_id": conflict_scan.id if conflict_scan else "unknown",
                "child_id": child.id,
                "age_category": norm_age,
                "status": conflict_scan.sync_status if conflict_scan else "synced",
                "created_at": created_iso,
            },
        )

    created_iso = scan_record.created_at.isoformat() if scan_record.created_at else datetime.now(timezone.utc).isoformat()

    import os
    img_name = os.path.basename(scan_record.image_path) if scan_record.image_path else f"{scan_record.id}.jpg"
    img_url = f"https://poshanscan-backend.onrender.com/uploads/{img_name}"

    return ScanResultResponse(
        id=scan_record.id,
        scan_id=scan_record.id,
        client_scan_id=scan_record.client_scan_id,
        child_id=scan_record.child_id,
        age_category=scan_record.age_category,
        muac_estimate_mm=scan_record.muac_estimate_mm,
        risk_band=scan_record.risk_band,
        confidence_score=scan_record.confidence_score,
        created_at=created_iso,
        image_url=img_url,
        photo_url=img_url,
    )


@router.get("/{scan_id}", response_model=ScanResultResponse)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a single scan result by scan_id or client_scan_id.
    Matches frontend GET /scans/{scanId}
    """
    scan = db.query(Scan).filter(
        (Scan.id == scan_id) | (Scan.client_scan_id == scan_id)
    ).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan record not found.",
        )
    created_iso = scan.created_at.isoformat() if scan.created_at else datetime.now(timezone.utc).isoformat()
    import os
    img_name = os.path.basename(scan.image_path) if scan.image_path else f"{scan.id}.jpg"
    img_url = f"https://poshanscan-backend.onrender.com/uploads/{img_name}"

    return ScanResultResponse(
        id=scan.id,
        scan_id=scan.id,
        client_scan_id=scan.client_scan_id or scan.id,
        child_id=scan.child_id,
        age_category=scan.age_category or "child_6_59m",
        muac_estimate_mm=float(scan.muac_estimate_mm) if scan.muac_estimate_mm is not None else 0.0,
        risk_band=scan.risk_band or "NORMAL",
        confidence_score=float(scan.confidence_score) if scan.confidence_score is not None else 1.0,
        created_at=created_iso,
        image_url=img_url,
        photo_url=img_url,
    )
