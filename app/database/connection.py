import os
from urllib.parse import urlparse


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
