#!/usr/bin/env python
"""Seed 3 demo members with accounts and loans for System 7 testing.

This script is idempotent — safe to run multiple times.  It uses
ON CONFLICT … DO UPDATE so re-running overwrites demo data without
creating duplicates.

Usage:
    python scripts/seed_demo_members.py
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_connection


def _hash_phone(phone_number: str) -> str:
    return hashlib.sha256(phone_number.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Demo members
# ---------------------------------------------------------------------------
# member_001 uses a placeholder phone.  Replace with your real WhatsApp
# number (e.g. "whatsapp:+254712345678") for live testing.
DEMO_MEMBERS = [
    {
        "id": "member_001",
        "phone": "whatsapp:+254110923440",
        "display_name": "Peter Mwangi",
        "preferred_language": "mixed",
        "knowledge_level": "beginner",
    },
    {
        "id": "member_002",
        "phone": "whatsapp:+254700000002",
        "display_name": "James Ochieng",
        "preferred_language": "en",
        "knowledge_level": "intermediate",
    },
    {
        "id": "member_003",
        "phone": "whatsapp:+254700000003",
        "display_name": "Amina Hassan",
        "preferred_language": "mixed",
        "knowledge_level": "beginner",
    },
]

DEMO_ACCOUNTS = [
    # member_001 (Peter Mwangi - Small hardware shop owner)
    {"member_id": "member_001", "account_type": "savings", "account_name": "Regular Savings", "balance": 80000.00},
    {"member_id": "member_001", "account_type": "shares", "account_name": "Share Capital", "balance": 15000.00},
    # member_002
    {"member_id": "member_002", "account_type": "savings", "account_name": "Regular Savings", "balance": 78200.00},
    {"member_id": "member_002", "account_type": "shares", "account_name": "Share Capital", "balance": 45000.00},
    # member_003
    {"member_id": "member_003", "account_type": "savings", "account_name": "Regular Savings", "balance": 5800.00},
    {"member_id": "member_003", "account_type": "shares", "account_name": "Share Capital", "balance": 3000.00},
]

DEMO_LOANS = [
    {
        "member_id": "member_001",
        "loan_type": "development",
        "principal": 200000.00,
        "balance_remaining": 125000.00,
        "monthly_instalment": 4500.00,
        "interest_rate": 12.00,
        "term_months": 48,
        "months_paid": 18,
        "status": "active",
    },
    {
        "member_id": "member_002",
        "loan_type": "school_fees",
        "principal": 80000.00,
        "balance_remaining": 50000.00,
        "monthly_instalment": 3500.00,
        "interest_rate": 10.00,
        "term_months": 24,
        "months_paid": 9,
        "status": "active",
    },
    # member_003 has no loans
]


def seed() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        # --- Members ---
        for m in DEMO_MEMBERS:
            phone_hash = _hash_phone(m["phone"])
            cur.execute(
                """
                INSERT INTO members (id, phone_hash, display_name, preferred_language,
                                     knowledge_level, sacco_id, is_demo)
                VALUES (%s, %s, %s, %s, %s, 'demo_sacco', true)
                ON CONFLICT (id) DO UPDATE SET
                    phone_hash = EXCLUDED.phone_hash,
                    display_name = EXCLUDED.display_name,
                    preferred_language = EXCLUDED.preferred_language,
                    knowledge_level = EXCLUDED.knowledge_level,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (m["id"], phone_hash, m["display_name"], m["preferred_language"], m["knowledge_level"]),
            )
            print(f"  Seeded member {m['id']} ({m['display_name']})")

        # --- Accounts (delete + re-insert for idempotency) ---
        member_ids = [m["id"] for m in DEMO_MEMBERS]
        cur.execute(
            "DELETE FROM member_accounts WHERE member_id = ANY(%s) AND is_demo = true",
            (member_ids,),
        )
        for a in DEMO_ACCOUNTS:
            cur.execute(
                """
                INSERT INTO member_accounts (member_id, account_type, account_name, balance,
                                             currency, is_demo)
                VALUES (%s, %s, %s, %s, 'KES', true)
                """,
                (a["member_id"], a["account_type"], a["account_name"], a["balance"]),
            )
        print(f"  Seeded {len(DEMO_ACCOUNTS)} demo accounts")

        # --- Loans (delete + re-insert for idempotency) ---
        cur.execute(
            "DELETE FROM member_loans WHERE member_id = ANY(%s) AND is_demo = true",
            (member_ids,),
        )
        for loan in DEMO_LOANS:
            cur.execute(
                """
                INSERT INTO member_loans (member_id, loan_type, principal, balance_remaining,
                                          monthly_instalment, interest_rate, term_months,
                                          months_paid, status, currency, is_demo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'KES', true)
                """,
                (
                    loan["member_id"],
                    loan["loan_type"],
                    loan["principal"],
                    loan["balance_remaining"],
                    loan["monthly_instalment"],
                    loan["interest_rate"],
                    loan["term_months"],
                    loan["months_paid"],
                    loan["status"],
                ),
            )
        print(f"  Seeded {len(DEMO_LOANS)} demo loans")

    print("Done.")


if __name__ == "__main__":
    seed()
