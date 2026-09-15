#!/usr/bin/env python
"""Seed engagement preferences and trusted financial news articles for System 10 testing.

Usage:
    python scripts/seed_demo_engagement.py
"""

from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_connection

NOW = datetime.now(timezone.utc)

DEMO_PREFERENCES = [
    {
        "member_id": "member_001",
        "education_frequency": "weekly",
        "news_frequency": "weekly",
        "goal_alerts_enabled": True,
        "allowed_topics": ["budgeting", "saving", "compound_interest", "emergency_fund"],
        "quiet_hours_start": 20,
        "quiet_hours_end": 8,
        "preferred_language": "en",
    },
    {
        "member_id": "member_002",
        "education_frequency": "biweekly",
        "news_frequency": "monthly",
        "goal_alerts_enabled": True,
        "allowed_topics": ["retirement", "debt_management", "asset_purchase", "sacco_shares"],
        "quiet_hours_start": 21,
        "quiet_hours_end": 7,
        "preferred_language": "en",
    },
    {
        "member_id": "member_003",
        "education_frequency": "weekly",
        "news_frequency": "paused",
        "goal_alerts_enabled": True,
        "allowed_topics": ["budgeting", "saving", "emergency_fund"],
        "quiet_hours_start": 20,
        "quiet_hours_end": 8,
        "preferred_language": "sw",
    },
]

DEMO_ARTICLES = [
    {
        "id": "art_cbk_rates_001",
        "source": "Central Bank of Kenya",
        "title": "CBK Retains Central Bank Benchmark Rate at 12.75%",
        "content": (
            "The Monetary Policy Committee (MPC) of the Central Bank of Kenya met on August 6, 2026, "
            "and decided to retain the Central Bank Rate (CBR) at 12.75 percent. The Committee noted "
            "that overall inflation remains anchored within the target range of 5.0 plus or minus 2.5 percent, "
            "and commercial bank lending rates have stabilized across major sectors."
        ),
        "summary": "CBK retains benchmark rate at 12.75% as inflation remains within target, stabilizing lending rates.",
        "category": "interest_rates",
        "url": "https://www.centralbank.go.ke/policy/rates",
        "published_at": NOW - timedelta(days=5),
        "expiry_at": NOW + timedelta(days=60),
        "is_approved": True,
    },
    {
        "id": "art_sasra_reg_002",
        "source": "SASRA",
        "title": "SASRA Issues Updated Financial Soundness and Capital Adequacy Directives",
        "content": (
            "The SACCO Societies Regulatory Authority (SASRA) has issued updated prudential standards "
            "for regulated SACCOs in Kenya. Regulated cooperatives are required to maintain core capital of "
            "at least KSh 10 million and maintain an institutional capital to total assets ratio of not less than 8 percent. "
            "The move strengthens depositor protection and long-term liquidity."
        ),
        "summary": "SASRA updates capital adequacy standards to protect member deposits and reinforce liquidity.",
        "category": "sacco_regulations",
        "url": "https://www.sasra.go.ke/prudential-standards",
        "published_at": NOW - timedelta(days=10),
        "expiry_at": NOW + timedelta(days=90),
        "is_approved": True,
    },
    {
        "id": "art_rba_pension_003",
        "source": "Business Daily",
        "title": "Retirement Benefits Authority Reports Surge in Cooperative Pension Assets",
        "content": (
            "Retirement sector assets held by cooperative and SACCO-backed schemes surpassed KSh 1.8 trillion "
            "in the latest financial review. Financial analysts attribute the steady growth to compounding returns "
            "on diversified fixed-income securities and disciplined voluntary contributions from informal and formal workers."
        ),
        "summary": "Retirement assets across cooperative schemes surge to KSh 1.8 trillion supported by consistent compounding.",
        "category": "retirement",
        "url": "https://www.businessdailyafrica.com/pension-growth",
        "published_at": NOW - timedelta(days=3),
        "expiry_at": NOW + timedelta(days=45),
        "is_approved": True,
    },
    {
        "id": "art_knbs_inflation_004",
        "source": "KNBS",
        "title": "Kenya Overall Year-on-Year Inflation Eases to 4.4%",
        "content": (
            "Kenya National Bureau of Statistics (KNBS) data shows overall year-on-year inflation eased to 4.4 percent "
            "for the month. The decline was supported by favorable rainfall stabilizing food prices and lower international "
            "fuel pump adjustments, giving households headroom to build emergency savings reserves."
        ),
        "summary": "Year-on-year inflation eases to 4.4 percent, easing household budget pressures and aiding emergency savings.",
        "category": "inflation",
        "url": "https://www.knbs.or.ke/cpi-report",
        "published_at": NOW - timedelta(days=2),
        "expiry_at": NOW + timedelta(days=30),
        "is_approved": True,
    },
]


def seed() -> None:
    print("Seeding System 10 Engagement Preferences and News...")
    with get_connection() as conn, conn.cursor() as cur:
        # Seed Preferences
        for p in DEMO_PREFERENCES:
            cur.execute(
                """
                INSERT INTO member_engagement_preferences (
                    member_id, education_frequency, news_frequency, goal_alerts_enabled,
                    allowed_topics, quiet_hours_start, quiet_hours_end, preferred_language,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (member_id) DO UPDATE SET
                    education_frequency = EXCLUDED.education_frequency,
                    news_frequency = EXCLUDED.news_frequency,
                    goal_alerts_enabled = EXCLUDED.goal_alerts_enabled,
                    allowed_topics = EXCLUDED.allowed_topics,
                    quiet_hours_start = EXCLUDED.quiet_hours_start,
                    quiet_hours_end = EXCLUDED.quiet_hours_end,
                    preferred_language = EXCLUDED.preferred_language,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    p["member_id"],
                    p["education_frequency"],
                    p["news_frequency"],
                    p["goal_alerts_enabled"],
                    p["allowed_topics"],
                    p["quiet_hours_start"],
                    p["quiet_hours_end"],
                    p["preferred_language"],
                ),
            )
            print(f"  Seeded preferences for {p['member_id']}")

        # Seed News Articles
        for a in DEMO_ARTICLES:
            cur.execute(
                """
                INSERT INTO financial_news_articles (
                    id, source, title, content, summary, category, url,
                    published_at, retrieved_at, expiry_at, is_approved
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    content = EXCLUDED.content,
                    expiry_at = EXCLUDED.expiry_at,
                    is_approved = EXCLUDED.is_approved
                """,
                (
                    a["id"],
                    a["source"],
                    a["title"],
                    a["content"],
                    a["summary"],
                    a["category"],
                    a["url"],
                    a["published_at"],
                    a["expiry_at"],
                    a["is_approved"],
                ),
            )
            print(f"  Seeded article {a['id']} ({a['title'][:40]}...)")

    print("System 10 Engagement Seed complete.")


if __name__ == "__main__":
    seed()
