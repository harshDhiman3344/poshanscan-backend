from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.child import Child
from app.models.scan import Scan
from app.schemas.child import (
    ChildCreate,
    ChildResponse,
    ChildScanSummary,
    ChildScanStatusResponse,
)

router = APIRouter(prefix="/children", tags=["Children"])


@router.get("/search", response_model=List[ChildResponse])
def search_children(
    q: Optional[str] = Query("", description="Search term for name, guardian, village, or ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search child records by name, guardian, village, or child ID.
    Includes scan status summaries so worker app knows whether a person has already been scanned.
    Matches Navya's GET /children/search?q=
    """
    query = db.query(Child)
    if q:
        search_pattern = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                Child.name.ilike(search_pattern),
                Child.guardian_name.ilike(search_pattern),
                Child.village.ilike(search_pattern),
                Child.id.ilike(search_pattern),
            )
        )
    
    results = query.limit(30).all()
    if not results:
        return []

    child_ids = [c.id for c in results]
    scans = db.query(Scan).filter(Scan.child_id.in_(child_ids)).all()
    scans_by_child: Dict[str, List[Scan]] = {}
    for s in scans:
        scans_by_child.setdefault(s.child_id, []).append(s)

    items = []
    for c in results:
        c_scans = scans_by_child.get(c.id, [])
        has_child = any((s.age_category or "child_6_59m") == "child_6_59m" for s in c_scans)
        has_adult = any((s.age_category or "child_6_59m") == "adult" for s in c_scans)
        summaries = [
            ChildScanSummary(
                scan_id=s.id,
                age_category=s.age_category or "child_6_59m",
                status=s.sync_status or "synced",
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in c_scans
        ]
        items.append(
            ChildResponse(
                id=c.id,
                child_id=c.id,
                name=c.name,
                dob=c.dob,
                gender=c.gender,
                guardian_name=c.guardian_name,
                village=c.village,
                has_child_scan=has_child,
                has_adult_scan=has_adult,
                scans=summaries,
            )
        )
    return items


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def register_child(
    child_in: ChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new child in the system.
    Matches Navya's POST /children
    """
    new_child = Child(
        name=child_in.name,
        dob=child_in.dob,
        gender=child_in.gender,
        guardian_name=child_in.guardian_name,
        village=child_in.village,
        registered_by=current_user.id,
        location_id=current_user.location_id,
    )
    db.add(new_child)
    db.commit()
    db.refresh(new_child)

    return ChildResponse(
        id=new_child.id,
        child_id=new_child.id,
        name=new_child.name,
        dob=new_child.dob,
        gender=new_child.gender,
        guardian_name=new_child.guardian_name,
        village=new_child.village,
        has_child_scan=False,
        has_adult_scan=False,
        scans=[],
    )


@router.get("/{child_id}/scan-status", response_model=ChildScanStatusResponse)
def get_child_scan_status(
    child_id: str,
    age_category: Optional[str] = Query(None, description="Optional age category to check specifically ('child_6_59m' or 'adult')"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Authenticated endpoint for the worker app to check if a person has already been scanned.
    Returns existing scan ID and status without exposing sensitive measurements or photos.
    """
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    scans = db.query(Scan).filter(Scan.child_id == child_id).all()
    summaries = [
        ChildScanSummary(
            scan_id=s.id,
            age_category=s.age_category or "child_6_59m",
            status=s.sync_status or "synced",
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in scans
    ]

    has_scanned = len(scans) > 0
    already_scanned = False
    existing_scan_id = None
    existing_status = None
    existing_created_at = None

    norm_age = None
    if age_category:
        norm_age = "adult" if str(age_category).strip().lower() == "adult" else "child_6_59m"
        match = next((s for s in scans if (s.age_category or "child_6_59m") == norm_age), None)
        if match:
            already_scanned = True
            existing_scan_id = match.id
            existing_status = match.sync_status
            existing_created_at = match.created_at.isoformat() if match.created_at else None

    return ChildScanStatusResponse(
        child_id=child.id,
        has_scanned=has_scanned,
        already_scanned=already_scanned,
        existing_scan_id=existing_scan_id,
        age_category=norm_age,
        status=existing_status,
        created_at=existing_created_at,
        scans=summaries,
    )


@router.get("/{child_id}", response_model=ChildResponse)
def get_child(
    child_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch single child record by ID with scan summaries."""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    c_scans = db.query(Scan).filter(Scan.child_id == child.id).all()
    has_child = any((s.age_category or "child_6_59m") == "child_6_59m" for s in c_scans)
    has_adult = any((s.age_category or "child_6_59m") == "adult" for s in c_scans)
    summaries = [
        ChildScanSummary(
            scan_id=s.id,
            age_category=s.age_category or "child_6_59m",
            status=s.sync_status or "synced",
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in c_scans
    ]

    return ChildResponse(
        id=child.id,
        child_id=child.id,
        name=child.name,
        dob=child.dob,
        gender=child.gender,
        guardian_name=child.guardian_name,
        village=child.village,
        has_child_scan=has_child,
        has_adult_scan=has_adult,
        scans=summaries,
    )
