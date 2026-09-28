import os
from urllib.parse import parse_qs, urlparse
import psycopg2


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/sacco")


def get_connection_params(url: str | None = None) -> dict:
    url = url or get_database_url()
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    params: dict = {
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }

    # Support Unix socket in query param (e.g. host=/cloudsql/PROJECT:REGION:INSTANCE)
    if "host" in query_params:
        params["host"] = query_params["host"][0]
    elif parsed.hostname:
        params["host"] = parsed.hostname
        params["port"] = parsed.port or 5432

    # Remove None values
    return {k: v for k, v in params.items() if v is not None}


def get_connection():
    """Open a PostgreSQL connection using the configured database URL.

    Supports Cloud SQL Unix sockets, Cloud SQL Auth Proxy, and standard TCP URLs.
    """
    from app.config.settings import settings

    url = settings.database_url or get_database_url()
    try:
        # psycopg2.connect natively accepts full DSN strings including Unix sockets & sslmode
        return psycopg2.connect(url)
    except Exception:
        # Fallback to parsed parameter mapping
        return psycopg2.connect(**get_connection_params(url))

