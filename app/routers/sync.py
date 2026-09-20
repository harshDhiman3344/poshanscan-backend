import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.child import Child
from app.models.scan import Scan
from app.schemas.scan import SyncScanItemResponse
from app.services.storage import save_upload_file
from app.services.cv_client import run_cv_inference, CVInferenceError

logger = logging.getLogger("poshanscan-backend.sync")
router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("", response_model=List[SyncScanItemResponse])
async def sync_offline_scans(
    metadata: str = Form(..., description="JSON-serialized array of scan metadata"),
    images: List[UploadFile] = File(..., description="List of images matching queued scans"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ingest batch of offline scans queued by Navya's worker app.
    Matches POST /sync (multipart): `metadata` is JSON array, `images` has one file per item.
    Returns per-item results or errors matched by client_scan_id.
    """
    try:
        meta_list = json.loads(metadata)
    except Exception as exc:
        logger.error("Failed to parse sync metadata JSON: %s", exc)
        return [
            SyncScanItemResponse(
                error="invalid_metadata_json",
                message="The metadata field must be a valid JSON array.",
            )
        ]

    # Map images by filename or index
    image_map = {}
    for idx, img in enumerate(images):
        fname = img.filename or ""
        stem = fname.rsplit(".", 1)[0]
        image_map[stem] = img
        image_map[f"index_{idx}"] = img

    results: List[SyncScanItemResponse] = []

    for idx, item in enumerate(meta_list):
        client_scan_id = item.get("client_scan_id")
        child_id = item.get("child_id")
        worker_id = item.get("worker_id", current_user.id)
        captured_at = item.get("captured_at")
        ref_type = item.get("reference_type", "aruco")
        ref_size = float(item.get("reference_size_mm", 50.0))

        # Check for idempotency: if this client_scan_id already exists in DB, return existing record
        if client_scan_id:
            existing = db.query(Scan).filter(Scan.client_scan_id == client_scan_id).first()
            if existing:
                created_iso = (
                    existing.created_at.isoformat()
                    if existing.created_at
                    else datetime.now(timezone.utc).isoformat()
                )
                results.append(
                    SyncScanItemResponse(
                        client_scan_id=client_scan_id,
                        scan_id=existing.id,
                        child_id=existing.child_id,
                        muac_estimate_mm=existing.muac_estimate_mm,
                        risk_band=existing.risk_band,
                        confidence_score=existing.confidence_score,
                        created_at=created_iso,
                    )
                )
                continue

        # Find corresponding image
        img = image_map.get(client_scan_id) or image_map.get(f"index_{idx}")
        if not img:
            results.append(
                SyncScanItemResponse(
                    client_scan_id=client_scan_id,
                    error="missing_image",
                    message="No corresponding image file uploaded for this scan.",
                )
            )
            continue

        try:
            image_bytes = await img.read()
            image_path = save_upload_file(image_bytes, img.filename or f"{client_scan_id}.jpg")
            
            cv_res = await run_cv_inference(
                image_bytes=image_bytes,
                filename=img.filename or f"{client_scan_id}.jpg",
                reference_type=ref_type,
                reference_size_mm=ref_size,
            )

            raw_band = (cv_res.risk_band or "NORMAL").upper()
            normalized_band = "NORMAL" if "NORM" in raw_band else ("MAM" if "MAM" in raw_band else "SAM")

            scan_rec = Scan(
                client_scan_id=client_scan_id,
                child_id=child_id,
                worker_id=worker_id,
                image_path=image_path,
                muac_estimate_mm=cv_res.muac_estimate_mm,
                risk_band=normalized_band,
                confidence_score=cv_res.confidence_score,
                quality_flags=cv_res.quality_flags.model_dump() if cv_res.quality_flags else None,
                sync_status="synced",
                captured_at=captured_at,
            )
            db.add(scan_rec)
            db.commit()
            db.refresh(scan_rec)

            created_iso = (
                scan_rec.created_at.isoformat()
                if scan_rec.created_at
                else datetime.now(timezone.utc).isoformat()
            )

            results.append(
                SyncScanItemResponse(
                    client_scan_id=client_scan_id,
                    scan_id=scan_rec.id,
                    child_id=scan_rec.child_id,
                    muac_estimate_mm=scan_rec.muac_estimate_mm,
                    risk_band=scan_rec.risk_band,
                    confidence_score=scan_rec.confidence_score,
                    created_at=created_iso,
                )
            )
        except CVInferenceError as exc:
            results.append(
                SyncScanItemResponse(
                    client_scan_id=client_scan_id,
                    error=exc.error,
                    message=exc.message,
                )
            )
        except Exception as exc:
            logger.exception("Unexpected error syncing scan %s", client_scan_id)
            results.append(
                SyncScanItemResponse(
                    client_scan_id=client_scan_id,
                    error="processing_failed",
                    message=str(exc),
                )
            )

    return results
