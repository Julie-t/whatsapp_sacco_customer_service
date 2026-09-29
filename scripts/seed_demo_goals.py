#!/usr/bin/env python
"""Seed demo financial goals for System 8 testing.

This script is idempotent — safe to run multiple times using ON CONFLICT DO UPDATE.

Usage:
    python scripts/seed_demo_goals.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_connection

DEMO_GOALS = [
    {
        "id": "goal_001_edu",
        "member_id": "member_001",
        "goal_type": "education",
        "name": "Daughter's University",
        "target_amount": 300000.00,
        "current_amount": 60000.00,
        "target_date": date.today() + timedelta(days=730),  # ~2 years
        "contribution_amount": 10000.00,
        "contribution_frequency": "monthly",
        "status": "active",
        "notification_frequency": "monthly",
        "notes": "Target for 2028 university enrollment",
    },
    {
        "id": "goal_002_emg",
        "member_id": "member_002",
        "goal_type": "emergency_fund",
        "name": "6-Month Emergency Buffer",
        "target_amount": 150000.00,
        "current_amount": 78200.00,
        "target_date": date.today() + timedelta(days=365),  # ~1 year
        "contribution_amount": 6000.00,
        "contribution_frequency": "monthly",
        "status": "active",
        "notification_frequency": "monthly",
        "notes": "Building 6 months of household expenses",
    },
    {
        "id": "goal_003_biz",
        "member_id": "member_003",
        "goal_type": "business",
        "name": "Inventory Expansion",
        "target_amount": 100000.00,
        "current_amount": 5800.00,
        "target_date": date.today() + timedelta(days=540),  # ~1.5 years
        "contribution_amount": 5000.00,
        "contribution_frequency": "monthly",
        "status": "active",
        "notification_frequency": "monthly",
        "notes": "Duka restock and shelf expansion",
    },
]


def seed() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        for g in DEMO_GOALS:
            cur.execute(
                """
                INSERT INTO financial_goals (
                    id, member_id, goal_type, name, target_amount, current_amount,
                    target_date, contribution_amount, contribution_frequency,
                    status, notification_frequency, notes, is_demo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (id) DO UPDATE SET
                    member_id = EXCLUDED.member_id,
                    goal_type = EXCLUDED.goal_type,
                    name = EXCLUDED.name,
                    target_amount = EXCLUDED.target_amount,
                    current_amount = EXCLUDED.current_amount,
                    target_date = EXCLUDED.target_date,
                    contribution_amount = EXCLUDED.contribution_amount,
                    contribution_frequency = EXCLUDED.contribution_frequency,
                    status = EXCLUDED.status,
                    notification_frequency = EXCLUDED.notification_frequency,
                    notes = EXCLUDED.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    g["id"],
                    g["member_id"],
                    g["goal_type"],
                    g["name"],
                    g["target_amount"],
                    g["current_amount"],
                    g["target_date"],
                    g["contribution_amount"],
                    g["contribution_frequency"],
                    g["status"],
                    g["notification_frequency"],
                    g["notes"],
                ),
            )
            print(f"  Seeded goal {g['id']} for {g['member_id']} ({g['name']})")
    print(f"Done seeding {len(DEMO_GOALS)} demo goals.")


if __name__ == "__main__":
    seed()
