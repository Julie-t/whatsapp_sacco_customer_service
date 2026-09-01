#!/usr/bin/env python
"""Delete inactive conversations beyond the configured retention period."""

from app.config.settings import settings
from app.database.connection import get_connection


def main() -> int:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM conversations "
            "WHERE last_activity_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')",
            (settings.conversation_retention_days,),
        )
        evaluated = cursor.fetchone()[0]
        cursor.execute(
            "DELETE FROM conversations "
            "WHERE last_activity_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')",
            (settings.conversation_retention_days,),
        )
        deleted = cursor.rowcount
    print(f"Conversations evaluated: {evaluated}")
    print(f"Conversations deleted/archived: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
