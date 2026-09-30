"""Automated database bootstrap on application startup.

Applies versioned migrations (001-007) and provisions default admin and demo
data if not present. All operations are idempotent and safe to run on every boot.
"""

import logging
from pathlib import Path

from app.database.connection import get_connection

logger = logging.getLogger(__name__)


def bootstrap_database() -> bool:
    """Run pending PostgreSQL migrations and ensure demo accounts exist."""
    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    if not migrations_dir.exists():
        logger.warning("Migrations directory not found at %s", migrations_dir)
        return False

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        logger.warning("No migration files found in %s", migrations_dir)
        return False

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations "
                    "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.commit()

                for migration in migration_files:
                    cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (migration.name,))
                    if cur.fetchone():
                        continue
                    logger.info("Applying database migration: %s", migration.name)
                    sql = migration.read_text(encoding="utf-8")
                    cur.execute(sql)
                    cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
                    conn.commit()
                    logger.info("Applied migration: %s", migration.name)

        _seed_demo_data()
        return True
    except Exception as exc:
        logger.warning("Database bootstrap skipped or failed: %s", exc)
        return False


def _seed_demo_data() -> None:
    """Seed initial demo admin and members if not already populated."""
    try:
        from app.database.admin_repository import AdminRepository
        from app.models.admin import AdminRole
        from app.services.admin.admin_auth_service import hash_password

        repo = AdminRepository()
        admin = repo.get_admin_by_username("admin")
        if not admin:
            pw_hash = hash_password("SaccoAdmin2026!")
            repo.create_admin_user(
                id="admin_001",
                username="admin",
                password_hash=pw_hash,
                sacco_id="demo_sacco",
                email="admin@demosacco.co.ke",
                role=AdminRole.ADMIN,
            )
            logger.info("Provisioned default demo admin account: admin / SaccoAdmin2026!")

        staff = repo.get_admin_by_username("support_staff")
        if not staff:
            pw_hash = hash_password("Staff2026!")
            repo.create_admin_user(
                id="staff_002",
                username="support_staff",
                password_hash=pw_hash,
                sacco_id="demo_sacco",
                email="support@demosacco.co.ke",
                role=AdminRole.STAFF,
            )
            logger.info("Provisioned demo support staff account: support_staff / Staff2026!")

    except Exception as exc:
        logger.warning("Demo admin seeding skipped: %s", exc)

    # Seed demo members, accounts, and loans so the analytics dashboard displays meaningful KPIs
    try:
        from scripts.seed_demo_members import DEMO_MEMBERS, DEMO_ACCOUNTS, DEMO_LOANS, _hash_phone
        with get_connection() as conn:
            with conn.cursor() as cur:
                for m in DEMO_MEMBERS:
                    cur.execute(
                        """
                        INSERT INTO members (id, phone_hash, display_name, preferred_language, knowledge_level)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (m["id"], _hash_phone(m["phone"]), m["display_name"], m["preferred_language"], m["knowledge_level"]),
                    )
                for a in DEMO_ACCOUNTS:
                    cur.execute(
                        """
                        INSERT INTO member_accounts (member_id, account_type, account_name, balance)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (a["member_id"], a["account_type"], a["account_name"], a["balance"]),
                    )
                for l in DEMO_LOANS:
                    cur.execute(
                        """
                        INSERT INTO member_loans (member_id, loan_type, loan_name, principal_amount,
                                                 outstanding_balance, monthly_instalment, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (l["member_id"], l["loan_type"], l["loan_name"], l["principal_amount"],
                         l["outstanding_balance"], l["monthly_instalment"], l["status"]),
                    )
                conn.commit()
    except Exception as exc:
        logger.warning("Demo member seeding skipped: %s", exc)
