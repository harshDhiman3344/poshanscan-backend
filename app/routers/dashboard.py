import io
import os
import csv
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.child import Child
from app.models.scan import Scan
from app.models.location import Location
from app.schemas.dashboard import (
    OverviewStats,
    TrendItem,
    DashboardTrends,
    LocationAggregate,
    WorkerStats,
    FlaggedScan,
)

router = APIRouter(tags=["Supervisor Dashboard"])


def apply_age_filter(query, age_category: Optional[str]):
    """Filter scans by age category. Defaults to child_6_59m so adult demo scans don't distort dashboard metrics."""
    target = (age_category or "child_6_59m").strip().lower()
    if target == "adult":
        return query.filter(Scan.age_category == "adult")
    elif target in ("child", "child_6_59m"):
        return query.filter((Scan.age_category == "child_6_59m") | (Scan.age_category.is_(None)))
    elif target == "all":
        return query
    return query.filter((Scan.age_category == "child_6_59m") | (Scan.age_category.is_(None)))


@router.get("/overview", response_model=OverviewStats)
def get_overview_metrics(
    age_category: Optional[str] = Query(None, description="Age category filter ('child_6_59m', 'adult', 'all'). Defaults to child_6_59m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Overall screening statistics for supervisor dashboard (defaults to child scans)."""
    base_query = apply_age_filter(db.query(Scan), age_category)
    total = base_query.count()
    normal = base_query.filter(Scan.risk_band == "NORMAL").count()
    mam = base_query.filter(Scan.risk_band == "MAM").count()
    sam = base_query.filter(Scan.risk_band == "SAM").count()

    avg_conf = base_query.with_entities(func.avg(Scan.confidence_score)).scalar() or 0.0

    # Count today's screenings
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    screenings_today = base_query.filter(Scan.created_at >= start_of_day).count()
    active_workers = (
        base_query.filter(Scan.created_at >= start_of_day)
        .with_entities(Scan.worker_id)
        .distinct()
        .count()
    )
    if active_workers == 0:
        active_workers = db.query(User).filter(User.role == "worker").count()

    rounded_avg = round(float(avg_conf), 2)

    return OverviewStats(
        total_screenings=total,
        normal_count=normal,
        mam_count=mam,
        sam_count=sam,
        avg_confidence=rounded_avg,
        average_confidence=rounded_avg,
        screenings_today=screenings_today,
        active_workers=active_workers,
    )


@router.get("/trends", response_model=DashboardTrends)
def get_screening_trends(
    days: int = Query(14, ge=1, le=90),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    group_by: Optional[str] = Query(None),
    interval: Optional[str] = Query(None),
    age_category: Optional[str] = Query(None, description="Age category filter ('child_6_59m', 'adult', 'all'). Defaults to child_6_59m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Daily time-series screening numbers for Recharts visualization (excludes adult scans by default)."""
    now = datetime.now(timezone.utc)
    if from_date:
        try:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            start_dt = now - timedelta(days=days)
    else:
        start_dt = now - timedelta(days=days)

    if to_date:
        try:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        except Exception:
            end_dt = now
    else:
        end_dt = now

    base_query = apply_age_filter(db.query(Scan), age_category)
    scans = base_query.filter(Scan.created_at >= start_dt, Scan.created_at <= end_dt).all()

    # Pre-fill all days in range to ensure continuous chart line
    daily_map = {}
    curr = start_dt.date()
    end_date = end_dt.date()
    while curr <= end_date:
        daily_map[curr.strftime("%Y-%m-%d")] = {"total": 0, "normal": 0, "mam": 0, "sam": 0}
        curr += timedelta(days=1)

    for s in scans:
        d_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else None
        if d_str and d_str in daily_map:
            daily_map[d_str]["total"] += 1
            if s.risk_band == "NORMAL":
                daily_map[d_str]["normal"] += 1
            elif s.risk_band == "MAM":
                daily_map[d_str]["mam"] += 1
            elif s.risk_band == "SAM":
                daily_map[d_str]["sam"] += 1

    trends = [
        TrendItem(
            date=k,
            total=v["total"],
            normal=v["normal"],
            mam=v["mam"],
            sam=v["sam"],
        )
        for k, v in sorted(daily_map.items())
    ]
    return DashboardTrends(points=trends)


@router.get("/locations", response_model=List[LocationAggregate])
def get_location_aggregates(
    age_category: Optional[str] = Query(None, description="Age category filter. Defaults to child_6_59m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """
    Geographic malnutrition risk breakdown based on actual registered children and screenings.
    Dynamically groups by village without relying on static dummy locations.
    """
    # Only include villages where actual registered children exist
    child_villages = [
        v[0] for v in db.query(Child.village).filter(Child.village.isnot(None), Child.village != "").distinct().all()
    ]
    loc_records = {l.village.lower(): l for l in db.query(Location).all() if l.village}
    all_villages = list(dict.fromkeys([v for v in child_villages if v]))

    location_data = []
    for idx, v_name in enumerate(all_villages):
        loc = loc_records.get(v_name.lower())
        scans_q = (
            db.query(Scan)
            .join(Child, Scan.child_id == Child.id)
            .filter(func.lower(Child.village) == v_name.lower())
        )
        scans = apply_age_filter(scans_q, age_category).all()
        tot = len(scans)
        norm = sum(1 for s in scans if s.risk_band == "NORMAL")
        m = sum(1 for s in scans if s.risk_band == "MAM")
        s = sum(1 for s in scans if s.risk_band == "SAM")
        at_risk = m + s
        sam_pct = round((s / tot * 100.0), 1) if tot > 0 else 0.0

        lat = loc.latitude if loc and loc.latitude else (28.6500 + idx * 0.01)
        lng = loc.longitude if loc and loc.longitude else (77.1200 + idx * 0.01)
        block = loc.block if loc and loc.block else "Rajouri Garden"
        district = loc.district if loc and loc.district else "West Delhi"
        loc_id = loc.id if loc else f"loc-{idx+1}"

        location_data.append(
            LocationAggregate(
                location_id=loc_id,
                village=v_name,
                block=block,
                district=district,
                lat=lat,
                lng=lng,
                total_screenings=tot,
                normal=norm,
                mam=m,
                sam=s,
                prevalence_pct=sam_pct,
                total=tot,
                at_risk_count=at_risk,
                at_risk_percentage=round((at_risk / tot * 100.0), 1) if tot > 0 else 0.0,
            )
        )
    return location_data


@router.get("/workers", response_model=List[WorkerStats])
def get_worker_performance(
    age_category: Optional[str] = Query(None, description="Age category filter. Defaults to child_6_59m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Worker activity and screening counts based on real user activity."""
    workers = db.query(User).filter(User.role == "worker").all()
    stats = []
    for w in workers:
        base_q = apply_age_filter(db.query(Scan).filter(Scan.worker_id == w.id), age_category)
        total_scans = base_q.count()
        last_scan = (
            base_q.with_entities(Scan.created_at)
            .order_by(Scan.created_at.desc())
            .first()
        )
        last_active = last_scan[0].isoformat() if last_scan and last_scan[0] else datetime.now(timezone.utc).isoformat()

        avg_c = (
            base_q.with_entities(func.avg(Scan.confidence_score))
            .scalar() or 0.90
        )
        flagged = (
            base_q.filter((Scan.confidence_score < 0.60) | (Scan.risk_band == "SAM"))
            .count()
        )

        village = "Delhi"
        if w.location_id:
            loc = db.query(Location).filter(Location.id == w.location_id).first()
            if loc:
                village = loc.village
        else:
            child_v = (
                db.query(Child.village)
                .join(Scan, Scan.child_id == Child.id)
                .filter(Scan.worker_id == w.id, Child.village.isnot(None))
                .first()
            )
            if child_v and child_v[0]:
                village = child_v[0]

        stats.append(
            WorkerStats(
                worker_id=w.id,
                name=w.name,
                worker_name=w.name,
                phone=w.phone,
                village=village,
                total_screenings=total_scans,
                last_active_at=last_active,
                last_active=last_active,
                avg_confidence=round(float(avg_c), 2),
                flagged_count=flagged,
            )
        )
    return stats


@router.get("/flagged", response_model=List[FlaggedScan])
def get_flagged_scans(
    status: Optional[str] = Query(None),
    age_category: Optional[str] = Query(None, description="Filter by age category ('child_6_59m', 'adult', 'all')"),
    q: Optional[str] = Query(None, description="Search term for child name, ID, village, or worker"),
    all_screenings: bool = Query(False, description="Include all screenings regardless of status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """
    Scans requiring review or triage.
    Supports search query 'q' across child name, child ID, village, and worker name.
    Supplies accessible image URLs so photos are viewable and zoomable in the supervisor dashboard.
    """
    query = (
        db.query(Scan, Child, User)
        .join(Child, Scan.child_id == Child.id)
        .join(User, Scan.worker_id == User.id)
    )

    # Search filter across child name, ID, village, worker
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Child.name).ilike(term),
                func.lower(Child.id).ilike(term),
                func.lower(Child.village).ilike(term),
                func.lower(User.name).ilike(term),
            )
        )
    elif not all_screenings and status == "flagged_only":
        query = query.filter((Scan.confidence_score < 0.60) | (Scan.risk_band == "SAM"))

    if status == "reviewed":
        query = query.filter(Scan.sync_status == "reviewed")
    elif status == "pending":
        query = query.filter(Scan.sync_status != "reviewed")

    if age_category:
        norm_cat = age_category.strip().lower()
        if norm_cat == "adult":
            query = query.filter(Scan.age_category == "adult")
        elif norm_cat in ("child", "child_6_59m"):
            query = query.filter((Scan.age_category == "child_6_59m") | (Scan.age_category.is_(None)))

    # Sort SAM and low-confidence first, then newest
    scans = (
        query.order_by(
            case((Scan.risk_band == "SAM", 1), (Scan.confidence_score < 0.60, 2), else_=3),
            Scan.created_at.desc(),
        )
        .limit(100)
        .all()
    )

    flagged = []
    for s, c, w in scans:
        flags: List[str] = []
        if isinstance(s.quality_flags, list):
            flags = [str(x) for x in s.quality_flags]
        elif isinstance(s.quality_flags, dict):
            neg_flags = [k.replace('_', ' ').title() for k, v in s.quality_flags.items() if v is False]
            flags = neg_flags if neg_flags else [f"{k}: {v}" for k, v in s.quality_flags.items()]
        elif isinstance(s.quality_flags, str) and s.quality_flags:
            flags = [s.quality_flags]

        if not flags:
            if s.confidence_score is not None and s.confidence_score < 0.60:
                flags.append("Low confidence reading")
            if s.risk_band == "SAM":
                flags.append("Severe Acute Malnutrition")
            elif s.risk_band == "MAM":
                flags.append("Moderate Acute Malnutrition")
            else:
                flags.append("Normal nutrition status")

        created_str = s.created_at.isoformat() if s.created_at else ""
        item_status = "reviewed" if s.sync_status == "reviewed" else "pending"

        # Construct image URL
        img_name = os.path.basename(s.image_path) if s.image_path else f"{s.id}.jpg"
        img_url = f"https://poshanscan-backend.onrender.com/uploads/{img_name}"

        flagged.append(
            FlaggedScan(
                screening_id=s.id,
                scan_id=s.id,
                child_ref=c.name,
                child_id=c.id,
                child_name=c.name,
                worker_id=w.id,
                worker_name=w.name,
                village=c.village or "rajouri",
                image_url=img_url,
                photo_url=img_url,
                media_url=img_url,
                age_category=s.age_category or "child_6_59m",
                muac_estimate_mm=s.muac_estimate_mm,
                risk_band=s.risk_band.capitalize() if s.risk_band == "NORMAL" else s.risk_band,
                confidence=s.confidence_score,
                confidence_score=s.confidence_score,
                sharpness=round(s.confidence_score * 100, 1) if s.confidence_score else 85.0,
                quality_score=round(s.confidence_score * 100, 1) if s.confidence_score else 85.0,
                reason="; ".join(flags),
                quality_flags=flags,
                status=item_status,
                captured_at=s.captured_at or created_str,
                created_at=created_str,
            )
        )
    return flagged


@router.post("/flagged/{scan_id}/review")
def review_flagged_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Mark a flagged scan as reviewed by supervisor."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if scan:
        scan.sync_status = "reviewed"
        db.commit()
    return {"success": True}


@router.get("/export")
def export_screenings_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Export all screenings to CSV for district health officials."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Scan ID",
        "Created At",
        "Child ID",
        "Child Name",
        "DOB",
        "Gender",
        "Village",
        "Worker ID",
        "Worker Name",
        "Age Category",
        "MUAC (mm)",
        "Risk Band",
        "Confidence Score",
        "Sync Status"
    ])

    rows = (
        db.query(Scan, Child, User)
        .join(Child, Scan.child_id == Child.id)
        .join(User, Scan.worker_id == User.id)
        .order_by(Scan.created_at.desc())
        .all()
    )

    for s, c, w in rows:
        writer.writerow([
            s.id,
            s.created_at.isoformat() if s.created_at else "",
            c.id,
            c.name,
            c.dob,
            c.gender,
            c.village or "",
            w.id,
            w.name,
            s.age_category or "child_6_59m",
            s.muac_estimate_mm,
            s.risk_band,
            s.confidence_score,
            s.sync_status
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=poshanscan_screenings.csv"}
    )
