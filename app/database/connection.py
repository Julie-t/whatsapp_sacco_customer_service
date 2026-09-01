import os
from urllib.parse import urlparse
import psycopg2

def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/sacco")

def get_connection_params(url: str | None = None):
    url = url or get_database_url()
    parsed = urlparse(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
        "host": parsed.hostname,
        "port": parsed.port or 5432,
    }

def get_connection():
    """Open a PostgreSQL connection using the configured database URL."""
    from app.config.settings import settings

    return psycopg2.connect(**get_connection_params(settings.database_url))
