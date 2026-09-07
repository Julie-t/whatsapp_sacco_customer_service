#!/usr/bin/env python
"""Apply versioned PostgreSQL migrations without changing schema at startup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_connection


def main() -> int:
    migrations_dir = Path(__file__).parent.parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print("No migrations found.")
        return 1

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            for migration in migration_files:
                cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (migration.name,))
                if cursor.fetchone():
                    continue
                cursor.execute(migration.read_text(encoding="utf-8"))
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
                print(f"Applied {migration.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
