from datetime import datetime, timezone, timedelta
import random
from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.location import Location
from app.models.child import Child
from app.models.scan import Scan


def seed():
    """Seed comprehensive dataset for PoshanScan so supervisor dashboard is fully populated."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("[*] Seeding PoshanScan Database...")

        # 1. Locations across Delhi/NCR with valid coordinates
        locations = [
            {"id": "loc-001", "village": "Rampur", "block": "Rajouri Garden", "district": "West Delhi", "lat": 28.6500, "lng": 77.1200},
            {"id": "loc-002", "village": "Khedi", "block": "Rajouri Garden", "district": "West Delhi", "lat": 28.6550, "lng": 77.1250},
            {"id": "loc-003", "village": "Sonpur", "block": "Rajouri Garden", "district": "West Delhi", "lat": 28.6600, "lng": 77.1300},
            {"id": "loc-004", "village": "Sitapur", "block": "Punjabi Bagh", "district": "West Delhi", "lat": 28.6850, "lng": 77.1400},
            {"id": "loc-005", "village": "Gopalpur", "block": "Najafgarh", "district": "South West Delhi", "lat": 28.6100, "lng": 77.0500},
            {"id": "loc-006", "village": "Madhapur", "block": "Janakpuri", "district": "West Delhi", "lat": 28.6250, "lng": 77.0850},
        ]
        for loc in locations:
            existing = db.query(Location).filter((Location.id == loc["id"]) | (Location.village == loc["village"])).first()
            if not existing:
                db.add(
                    Location(
                        id=loc["id"],
                        state="Delhi",
                        district=loc["district"],
                        block=loc["block"],
                        village=loc["village"],
                        anganwadi_center=f"{loc['village']} Center",
                        latitude=loc["lat"],
                        longitude=loc["lng"],
                    )
                )
            else:
                existing.latitude = loc["lat"]
                existing.longitude = loc["lng"]
                existing.block = loc["block"]
                existing.district = loc["district"]
        db.commit()

        # 2. Users (Supervisors + 4 Field Workers)
        super_users = [
            {"id": "b7c1f0a2-0000-4000-8000-000000000002", "name": "Dr. Alok Verma (Supervisor)", "phone": "9000000000", "pass": "super123", "role": "supervisor"},
            {"id": "admin-001", "name": "Admin Supervisor", "phone": "admin", "pass": "admin", "role": "admin"},
        ]
        for s in super_users:
            existing = db.query(User).filter((User.id == s["id"]) | (User.phone == s["phone"])).first()
            if not existing:
                db.add(User(id=s["id"], name=s["name"], phone=s["phone"], password_hash=get_password_hash(s["pass"]), role=s["role"], location_id="loc-001"))

        worker_users = [
            {"id": "b7c1f0a2-0000-4000-8000-000000000001", "name": "Rani Devi (Worker)", "phone": "9876543210", "pass": "worker123", "village": "Rampur", "loc": "loc-001"},
            {"id": "b7c1f0a2-0000-4000-8000-000000000003", "name": "Meena Kumari (Worker)", "phone": "9876543211", "pass": "worker123", "village": "Sitapur", "loc": "loc-004"},
            {"id": "b7c1f0a2-0000-4000-8000-000000000004", "name": "Sunita Rao (Worker)", "phone": "9876543212", "pass": "worker123", "village": "Gopalpur", "loc": "loc-005"},
            {"id": "b7c1f0a2-0000-4000-8000-000000000005", "name": "Asha Devi (Worker)", "phone": "9876543213", "pass": "worker123", "village": "Madhapur", "loc": "loc-006"},
        ]
        for w in worker_users:
            existing = db.query(User).filter((User.id == w["id"]) | (User.phone == w["phone"])).first()
            if not existing:
                db.add(User(id=w["id"], name=w["name"], phone=w["phone"], password_hash=get_password_hash(w["pass"]), role="worker", location_id=w["loc"]))
            else:
                existing.location_id = w["loc"]
        db.commit()

        # 3. Children Profiles
        sample_children = [
            {"name": "Aarav Kumar", "dob": "2024-06-15", "gender": "M", "guardian": "Sunita Kumar", "village": "Rampur"},
            {"name": "Diya Sharma", "dob": "2024-01-10", "gender": "F", "guardian": "Meena Sharma", "village": "Rampur"},
            {"name": "Vihaan Gupta", "dob": "2022-03-14", "gender": "M", "guardian": "Anita Gupta", "village": "Rampur"},
            {"name": "Priya Patel", "dob": "2024-02-18", "gender": "F", "guardian": "Geeta Patel", "village": "Sitapur"},
            {"name": "Rohan Joshi", "dob": "2023-11-05", "gender": "M", "guardian": "Radha Joshi", "village": "Sitapur"},
            {"name": "Aditya Mehra", "dob": "2023-04-12", "gender": "M", "guardian": "Kavita Mehra", "village": "Gopalpur"},
            {"name": "Sneha Nair", "dob": "2024-08-22", "gender": "F", "guardian": "Lalita Nair", "village": "Gopalpur"},
            {"name": "Arjun Das", "dob": "2023-09-30", "gender": "M", "guardian": "Kamla Das", "village": "Madhapur"},
            {"name": "Meera Sen", "dob": "2024-05-19", "gender": "F", "guardian": "Sarita Sen", "village": "Madhapur"},
            {"name": "Kabir Singh", "dob": "2023-08-20", "gender": "M", "guardian": "Poonam Singh", "village": "Khedi"},
            {"name": "Ananya Yadav", "dob": "2025-12-01", "gender": "F", "guardian": "Rekha Yadav", "village": "Khedi"},
            {"name": "Ishita Verma", "dob": "2026-06-05", "gender": "F", "guardian": "Kavita Verma", "village": "Sonpur"},
        ]

        for c in sample_children:
            existing = db.query(Child).filter(Child.name == c["name"]).first()
            if not existing:
                child = Child(
                    name=c["name"],
                    dob=c["dob"],
                    gender=c["gender"],
                    guardian_name=c["guardian"],
                    village=c["village"],
                    registered_by="b7c1f0a2-0000-4000-8000-000000000001",
                )
                db.add(child)
        db.commit()

        child_records = db.query(Child).all()

        # 4. Rich Screenings Dataset (150+ records over past 14 days, including today)
        current_scan_count = db.query(Scan).count()
        if current_scan_count < 50:
            print("  Generating rich historical screening data across all villages...")
            now = datetime.now(timezone.utc)
            worker_ids = [w["id"] for w in worker_users]
            
            flag_reasons = [
                "Motion blur detected",
                "Reference coin partially obscured",
                "Sub-optimal lighting",
                "Arm angle skewed",
                "Low contrast against arm surface",
            ]

            # Generate screenings across days: 0 (today) through 13 days ago
            for days_ago in range(14):
                # Today gets 16-20 scans across all 4 workers; earlier days get 8-12 scans
                num_scans = random.randint(16, 20) if days_ago == 0 else random.randint(8, 12)
                
                # Ensure all 4 workers are active today
                day_workers = worker_ids[:] if days_ago == 0 else [random.choice(worker_ids) for _ in range(num_scans)]

                for i in range(num_scans):
                    child = random.choice(child_records)
                    worker_id = day_workers[i] if days_ago == 0 and i < len(day_workers) else random.choice(worker_ids)
                    
                    # Distribute realistic MUAC values: 65% Normal, 22% MAM, 13% SAM
                    r = random.random()
                    flags = []
                    if r < 0.13:
                        muac = round(random.uniform(105.0, 114.5), 1)
                        band = "SAM"
                        flags = ["Severe Acute Malnutrition"]
                        if random.random() < 0.5:
                            flags.append(random.choice(flag_reasons))
                        conf = round(random.uniform(0.72, 0.89), 2)
                    elif r < 0.35:
                        muac = round(random.uniform(115.0, 124.5), 1)
                        band = "MAM"
                        if random.random() < 0.35:
                            flags.append(random.choice(flag_reasons))
                        conf = round(random.uniform(0.80, 0.94), 2)
                    else:
                        muac = round(random.uniform(125.0, 138.0), 1)
                        band = "NORMAL"
                        conf = round(random.uniform(0.88, 0.98), 2)

                    scan_time = now - timedelta(days=days_ago, hours=random.randint(0, 9), minutes=random.randint(1, 55))
                    
                    # Some older SAM records marked reviewed to test supervisor review flow
                    status = "reviewed" if (days_ago > 3 and band == "SAM" and random.random() < 0.4) else "synced"

                    scan = Scan(
                        child_id=child.id,
                        worker_id=worker_id,
                        muac_estimate_mm=muac,
                        risk_band=band,
                        confidence_score=conf,
                        quality_flags=flags,
                        sync_status=status,
                        captured_at=scan_time.isoformat(),
                        created_at=scan_time,
                    )
                    db.add(scan)
            db.commit()

        print("[+] Comprehensive database seeding completed!")
        print("   Supervisors: admin/admin or 9000000000/super123")
        print("   Workers:     9876543210 through 9876543213 / worker123")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
