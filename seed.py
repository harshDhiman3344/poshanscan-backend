from datetime import datetime, timezone, timedelta
import random
from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.location import Location
from app.models.child import Child
from app.models.scan import Scan


def seed():
    """Seed default database with test accounts, locations, children, and scans."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("[*] Seeding PoshanScan Database...")

        # 1. Locations
        loc_rampur = Location(
            id="loc-001",
            state="Delhi",
            district="West Delhi",
            block="Rajouri Garden",
            village="Rampur",
            anganwadi_center="Anganwadi Center 1",
            latitude=28.6500,
            longitude=77.1200,
        )
        loc_khedi = Location(
            id="loc-002",
            state="Delhi",
            district="West Delhi",
            block="Rajouri Garden",
            village="Khedi",
            anganwadi_center="Anganwadi Center 2",
            latitude=28.6550,
            longitude=77.1250,
        )
        loc_sonpur = Location(
            id="loc-003",
            state="Delhi",
            district="West Delhi",
            block="Rajouri Garden",
            village="Sonpur",
            anganwadi_center="Anganwadi Center 3",
            latitude=28.6600,
            longitude=77.1300,
        )
        for loc in [loc_rampur, loc_khedi, loc_sonpur]:
            if not db.query(Location).filter(Location.id == loc.id).first():
                db.add(loc)
        db.commit()

        # 2. Users (Worker & Supervisor matching Navya's mock server)
        worker_id = "b7c1f0a2-0000-4000-8000-000000000001"
        super_id = "b7c1f0a2-0000-4000-8000-000000000002"

        if not db.query(User).filter(User.phone == "9876543210").first():
            worker = User(
                id=worker_id,
                name="Rani Devi (Worker)",
                phone="9876543210",
                password_hash=get_password_hash("worker123"),
                role="worker",
                location_id="loc-001",
            )
            db.add(worker)

        if not db.query(User).filter(User.phone == "9000000000").first():
            supervisor = User(
                id=super_id,
                name="Dr. Alok Verma (Supervisor)",
                phone="9000000000",
                password_hash=get_password_hash("super123"),
                role="supervisor",
                location_id="loc-001",
            )
            db.add(supervisor)
        db.commit()

        # 3. Children (Matching Navya's mock server data)
        sample_children = [
            {"name": "Aarav Kumar", "dob": "2024-06-15", "gender": "M", "guardian_name": "Sunita Kumar", "village": "Rampur"},
            {"name": "Diya Sharma", "dob": "2024-01-10", "gender": "F", "guardian_name": "Meena Sharma", "village": "Rampur"},
            {"name": "Kabir Singh", "dob": "2023-08-20", "gender": "M", "guardian_name": "Poonam Singh", "village": "Khedi"},
            {"name": "Ananya Yadav", "dob": "2025-12-01", "gender": "F", "guardian_name": "Rekha Yadav", "village": "Khedi"},
            {"name": "Vihaan Gupta", "dob": "2022-03-14", "gender": "M", "guardian_name": "Anita Gupta", "village": "Rampur"},
            {"name": "Ishita Verma", "dob": "2026-06-05", "gender": "F", "guardian_name": "Kavita Verma", "village": "Sonpur"},
        ]

        child_records = []
        for c in sample_children:
            existing = db.query(Child).filter(Child.name == c["name"]).first()
            if not existing:
                child = Child(
                    name=c["name"],
                    dob=c["dob"],
                    gender=c["gender"],
                    guardian_name=c["guardian_name"],
                    village=c["village"],
                    registered_by=worker_id,
                )
                db.add(child)
                child_records.append(child)
            else:
                child_records.append(existing)
        db.commit()

        # 4. Sample Screenings for Dashboard Trends & Analytics
        if db.query(Scan).count() == 0:
            print("  Adding sample screening data...")
            now = datetime.now(timezone.utc)
            for c in child_records:
                # Add 2-3 screenings per child over past 10 days
                for days_ago in [8, 4, 1]:
                    muac = round(random.uniform(110.0, 132.0), 1)
                    if muac < 115.0:
                        band = "SAM"
                    elif muac < 125.0:
                        band = "MAM"
                    else:
                        band = "NORMAL"

                    scan = Scan(
                        child_id=c.id,
                        worker_id=worker_id,
                        muac_estimate_mm=muac,
                        risk_band=band,
                        confidence_score=round(random.uniform(0.78, 0.96), 2),
                        quality_flags={"reference_detected": True, "arm_detected": True, "segmentation_ok": True},
                        sync_status="synced",
                        created_at=now - timedelta(days=days_ago),
                    )
                    db.add(scan)
            db.commit()

        print("[+] Database seeding completed successfully!")
        print("   Worker:     9876543210 / worker123")
        print("   Supervisor: 9000000000 / super123")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
