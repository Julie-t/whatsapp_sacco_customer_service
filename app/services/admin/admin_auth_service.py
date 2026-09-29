"""Authentication and authorization services for SACCO staff dashboard."""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.config.settings import settings
from app.database.admin_repository import AdminRepository
from app.models.admin import AdminRole, AdminUser

logger = logging.getLogger(__name__)

AUTH_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", settings.twilio_auth_token or "sacco_admin_secret_key_2026")
TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7-day token expiration


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a cryptographically secure salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored salt:hash string."""
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


def create_access_token(admin_id: str, username: str, sacco_id: str, role: str) -> str:
    """Create a signed HMAC-SHA256 session token with expiration timestamp."""
    payload = {
        "admin_id": admin_id,
        "username": username,
        "sacco_id": sacco_id,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    token_bytes = f"{raw.decode('utf-8')}.{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(token_bytes).decode("utf-8")


def decode_access_token(token_str: str) -> Optional[dict]:
    """Decode and verify HMAC signature and expiration."""
    try:
        decoded = base64.urlsafe_b64decode(token_str.encode("utf-8")).decode("utf-8")
        raw, sig = decoded.rsplit(".", 1)
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(raw)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


class AdminAuthService:
    def __init__(self, repo: Optional[AdminRepository] = None):
        self.repo = repo or AdminRepository()

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        user = self.repo.get_admin_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None

        token = create_access_token(
            admin_id=user.id,
            username=user.username,
            sacco_id=user.sacco_id,
            role=user.role.value,
        )
        self.repo.record_audit(
            action="login",
            resource_type="admin_user",
            resource_id=user.id,
            admin_id=user.id,
            sacco_id=user.sacco_id,
            details={"username": user.username},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": user.username,
            "role": user.role,
            "sacco_id": user.sacco_id,
        }


def get_current_admin(
    authorization: Optional[str] = Header(None),
    repo: Optional[AdminRepository] = Depends(AdminRepository),
) -> AdminUser:
    """FastAPI dependency to authenticate and inject current AdminUser."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin = repo.get_admin_by_id(payload["admin_id"])
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or deactivated",
        )
    return admin
