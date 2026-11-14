import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("poshanscan-backend.migration")


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
