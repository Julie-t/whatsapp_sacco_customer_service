#!/usr/bin/env python
"""Seed default SACCO staff and administrator accounts for System 11."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.admin_repository import AdminRepository
from app.models.admin import AdminRole
from app.services.admin.admin_auth_service import hash_password

DEMO_ADMINS = [
    {
        "id": "admin_001",
        "username": "admin",
        "password": "SaccoAdmin2026!",
        "email": "admin@demosacco.co.ke",
        "sacco_id": "demo_sacco",
        "role": AdminRole.ADMIN,
    },
    {
        "id": "staff_002",
        "username": "support_staff",
        "password": "Staff2026!",
        "email": "support@demosacco.co.ke",
        "sacco_id": "demo_sacco",
        "role": AdminRole.STAFF,
    },
]


def seed():
    repo = AdminRepository()
    print("Seeding System 11 Admin and Staff accounts...")
    for item in DEMO_ADMINS:
        pw_hash = hash_password(item["password"])
        admin = repo.create_admin_user(
            id=item["id"],
            username=item["username"],
            password_hash=pw_hash,
            sacco_id=item["sacco_id"],
            email=item["email"],
            role=item["role"],
        )
        print(f"  Provisioned {admin.username} ({admin.role.value}) for SACCO '{admin.sacco_id}'")
    print("Done seeding admin accounts.")


if __name__ == "__main__":
    seed()
