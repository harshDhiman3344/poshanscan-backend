import io
import csv
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.child import Child
from app.models.scan import Scan
from app.schemas.dashboard import (
    OverviewStats,
    TrendItem,
    LocationAggregate,
    WorkerStats,
    FlaggedScan,
)

router = APIRouter(prefix="/dashboard", tags=["Supervisor Dashboard"])


@router.get("/overview", response_model=OverviewStats)
def get_overview_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Overall screening statistics for supervisor dashboard."""
    total = db.query(Scan).count()
    normal = db.query(Scan).filter(Scan.risk_band == "NORMAL").count()
    mam = db.query(Scan).filter(Scan.risk_band == "MAM").count()
    sam = db.query(Scan).filter(Scan.risk_band == "SAM").count()

    avg_conf = db.query(func.avg(Scan.confidence_score)).scalar() or 0.0

    return OverviewStats(
        total_screenings=total,
        normal_count=normal,
        mam_count=mam,
        sam_count=sam,
        average_confidence=round(float(avg_conf), 2),
    )


@router.get("/trends", response_model=List[TrendItem])
def get_screening_trends(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Daily time-series screening numbers for Recharts visualization."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scans = db.query(Scan).filter(Scan.created_at >= cutoff).all()

    daily_map = {}
    for s in scans:
        d_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else "Unknown"
        if d_str not in daily_map:
            daily_map[d_str] = {"total": 0, "normal": 0, "mam": 0, "sam": 0}
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
    return trends


@router.get("/locations", response_model=List[LocationAggregate])
def get_location_aggregates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Geographic malnutrition risk breakdown for Leaflet heatmaps."""
    # Join scans with children to group by village
    results = (
        db.query(
            Child.village,
            func.count(Scan.id).label("total"),
            func.sum(case((Scan.risk_band == "MAM", 1), else_=0)).label("mam"),
            func.sum(case((Scan.risk_band == "SAM", 1), else_=0)).label("sam"),
        )
        .join(Scan, Scan.child_id == Child.id)
        .group_by(Child.village)
        .all()
    )

    location_data = []
    for r in results:
        v_name = r[0] or "Unassigned Village"
        tot = r[1] or 0
        m = r[2] or 0
        s = r[3] or 0
        at_risk = m + s
        pct = round((at_risk / tot * 100.0), 1) if tot > 0 else 0.0
        location_data.append(
            LocationAggregate(
                village=v_name,
                total=tot,
                mam=m,
                sam=s,
                at_risk_count=at_risk,
                at_risk_percentage=pct,
            )
        )
    return location_data


@router.get("/workers", response_model=List[WorkerStats])
def get_worker_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Worker activity and screening counts."""
    workers = db.query(User).filter(User.role == "worker").all()
    stats = []
    for w in workers:
        total_scans = db.query(Scan).filter(Scan.worker_id == w.id).count()
        last_scan = (
            db.query(Scan.created_at)
            .filter(Scan.worker_id == w.id)
            .order_by(Scan.created_at.desc())
            .first()
        )
        last_active = last_scan[0].isoformat() if last_scan and last_scan[0] else None

        stats.append(
            WorkerStats(
                worker_id=w.id,
                worker_name=w.name,
                phone=w.phone,
                total_screenings=total_scans,
                last_active=last_active,
            )
        )
    return stats


@router.get("/flagged", response_model=List[FlaggedScan])
def get_flagged_scans(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["supervisor", "admin"])),
):
    """Scans requiring manual review (confidence < 0.60 or SAM)."""
    scans = (
        db.query(Scan, Child, User)
        .join(Child, Scan.child_id == Child.id)
        .join(User, Scan.worker_id == User.id)
        .filter((Scan.confidence_score < 0.60) | (Scan.risk_band == "SAM"))
        .order_by(Scan.created_at.desc())
        .limit(50)
        .all()
    )

    flagged = []
    for s, c, w in scans:
        reasons = []
        if s.confidence_score < 0.60:
            reasons.append(f"Low confidence ({s.confidence_score:.2f})")
        if s.risk_band == "SAM":
            reasons.append("Severe Acute Malnutrition (SAM)")

        flagged.append(
            FlaggedScan(
                scan_id=s.id,
                child_id=c.id,
                child_name=c.name,
                worker_id=w.id,
                worker_name=w.name,
                muac_estimate_mm=s.muac_estimate_mm,
                risk_band=s.risk_band,
                confidence_score=s.confidence_score,
                reason="; ".join(reasons),
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
        )
    return flagged


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
