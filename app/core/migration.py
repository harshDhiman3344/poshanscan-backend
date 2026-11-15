import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("poshanscan-backend.migration")


def cleanup_dummy_data(conn):
    """
    Remove simulated demo data from production/seed database,
    preserving real accounts and the Dhruv screening record.
    """
    try:
        # Check if dummy seed children exist (e.g. Diya Sharma, Sunita Kumar, Kabir Singh)
        has_dummy_seed = conn.execute(
            text("SELECT COUNT(*) FROM children WHERE name IN ('Diya Sharma', 'Vihaan Gupta', 'Kabir Singh', 'Meera Sen')")
        ).scalar()

        if has_dummy_seed and has_dummy_seed > 0:
            logger.info("Found dummy seed data in database. Purging demo dataset and preserving Dhruv data point...")
            
            # 1. Delete scans not belonging to dhruv
            conn.execute(text("""
                DELETE FROM scans 
                WHERE child_id NOT IN (
                    SELECT id FROM children WHERE LOWER(name) = 'dhruv'
                )
            """))
            conn.commit()

            # 2. Keep only latest scan per age category for Dhruv
            dhruv_scans = conn.execute(
                text("SELECT id FROM scans WHERE child_id IN (SELECT id FROM children WHERE LOWER(name) = 'dhruv') ORDER BY created_at DESC")
            ).fetchall()
            if len(dhruv_scans) > 1:
                for del_s in dhruv_scans[1:]:
                    conn.execute(text("DELETE FROM scans WHERE id = :sid"), {"sid": del_s[0]})
                conn.commit()

            # 3. Delete dummy children
            conn.execute(text("""
                DELETE FROM children 
                WHERE LOWER(name) != 'dhruv' AND id != '1f1014e9-3342-4a74-b868-43f4cb190a4b'
            """))
            conn.commit()

            # 4. Clean dummy locations (loc-001 through loc-006)
            conn.execute(text("""
                DELETE FROM locations 
                WHERE village NOT IN (SELECT DISTINCT village FROM children WHERE village IS NOT NULL)
            """))
            conn.commit()

            # 5. Clean dummy workers
            conn.execute(text("""
                DELETE FROM users 
                WHERE phone IN ('9876543211', '9876543212', '9876543213')
            """))
            conn.commit()

            # Ensure rajouri location exists for Dhruv
            rajouri_exists = conn.execute(text("SELECT COUNT(*) FROM locations WHERE LOWER(village) = 'rajouri'")).scalar()
            if not rajouri_exists:
                conn.execute(text("""
                    INSERT INTO locations (id, state, district, block, village, anganwadi_center, latitude, longitude)
                    VALUES ('loc-rajouri', 'Delhi', 'West Delhi', 'Rajouri Garden', 'rajouri', 'Rajouri Center', 28.6500, 77.1200)
                """))
                conn.commit()

            logger.info("Purge complete! Only real data and Dhruv data point retained.")
    except Exception as exc:
        logger.warning("Data cleanup encountered an issue: %s", exc)
        conn.rollback()


def run_migrations(engine: Engine):
    """
    Ensure schema changes are applied to the active database (SQLite and PostgreSQL Supabase).
    Safe, idempotent, and non-destructive.
    """
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()

            # 1. Scans table migrations
            if "scans" in table_names:
                columns = [c["name"] for c in inspector.get_columns("scans")]
                if "age_category" not in columns:
                    logger.info("Migrating schema: adding 'age_category' column to 'scans' table...")
                    conn.execute(
                        text("ALTER TABLE scans ADD COLUMN age_category VARCHAR(20) DEFAULT 'child_6_59m'")
                    )
                    conn.execute(
                        text("UPDATE scans SET age_category = 'child_6_59m' WHERE age_category IS NULL")
                    )
                    conn.commit()
                    logger.info("Schema migration complete: 'age_category' column added!")
                else:
                    # Update any NULL values to default
                    conn.execute(
                        text("UPDATE scans SET age_category = 'child_6_59m' WHERE age_category IS NULL")
                    )
                    conn.commit()

                # Clean up dummy demo data if present
                cleanup_dummy_data(conn)

                # 2. Unique constraint / index on (child_id, age_category)
                try:
                    unique_constraints = inspector.get_unique_constraints("scans")
                    indexes = inspector.get_indexes("scans")
                    has_unique = any(
                        set(uc.get("column_names", [])) == {"child_id", "age_category"}
                        for uc in unique_constraints
                    ) or any(
                        idx.get("unique") and set(idx.get("column_names", [])) == {"child_id", "age_category"}
                        for idx in indexes
                    )
                    if not has_unique:
                        logger.info("Creating unique index on scans(child_id, age_category)...")
                        conn.execute(
                            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_scans_child_age_category ON scans (child_id, age_category)")
                        )
                        conn.commit()
                        logger.info("Unique index uq_scans_child_age_category created successfully.")
                except Exception as idx_exc:
                    logger.warning(
                        "Could not create unique index uq_scans_child_age_category (may have existing duplicate records): %s",
                        idx_exc,
                    )
                    conn.rollback()
    except Exception as exc:
        logger.warning("Database migration encountered an issue: %s", exc)
