"""PostgreSQL-backed member repository."""

import hashlib
import logging

from app.database.connection import get_connection
from app.models.member import Member, MemberAccount, MemberLoan

logger = logging.getLogger(__name__)


def _hash_phone(phone_number: str) -> str:
    """Deterministic SHA-256 hash of a normalized phone number."""
    cleaned = phone_number.strip().replace(" ", "")
    if cleaned.startswith("whatsapp:") and not cleaned.startswith("whatsapp:+"):
        cleaned = "whatsapp:+" + cleaned[len("whatsapp:"):]
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


class MemberRepository:
    """Persistent member storage backed by PostgreSQL."""

    @staticmethod
    def get_by_phone(phone_number: str) -> Member | None:
        hashes = [_hash_phone(phone_number)]
        raw = phone_number.strip().replace(" ", "")
        if raw.startswith("whatsapp:"):
            hashes.append(_hash_phone(raw[len("whatsapp:"):]))
        else:
            hashes.append(_hash_phone(f"whatsapp:{raw}"))
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT id, phone_hash, display_name, preferred_language, "
                    "knowledge_level, sacco_id, is_demo, created_at, updated_at "
                    "FROM members WHERE phone_hash = ANY(%s)",
                    (hashes,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return Member(
                    id=row[0],
                    phone_hash=row[1],
                    display_name=row[2],
                    preferred_language=row[3],
                    knowledge_level=row[4],
                    sacco_id=row[5],
                    is_demo=row[6],
                    created_at=row[7],
                    updated_at=row[8],
                )
        except Exception:
            logger.exception("Failed to look up member by phone")
            return None

    @staticmethod
    def get_by_id(member_id: str) -> Member | None:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT id, phone_hash, display_name, preferred_language, "
                    "knowledge_level, sacco_id, is_demo, created_at, updated_at "
                    "FROM members WHERE id = %s",
                    (member_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return Member(
                    id=row[0],
                    phone_hash=row[1],
                    display_name=row[2],
                    preferred_language=row[3],
                    knowledge_level=row[4],
                    sacco_id=row[5],
                    is_demo=row[6],
                    created_at=row[7],
                    updated_at=row[8],
                )
        except Exception:
            logger.exception("Failed to look up member by id")
            return None

    @staticmethod
    def create_or_get_demo_member(
        phone_number: str,
        display_name: str = "Member",
        sacco_id: str = "demo_sacco",
    ) -> Member:
        """Ensure a demo member row exists in PostgreSQL for foreign key constraints."""
        phone_hash = _hash_phone(phone_number)
        demo_id = f"demo_{phone_hash[:8]}"
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO members (id, phone_hash, display_name, preferred_language, knowledge_level, sacco_id, is_demo)
                    VALUES (%s, %s, %s, 'en', 'beginner', %s, true)
                    ON CONFLICT (phone_hash) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                    RETURNING id, phone_hash, display_name, preferred_language, knowledge_level, sacco_id, is_demo, created_at, updated_at
                    """,
                    (demo_id, phone_hash, display_name, sacco_id),
                )
                row = cur.fetchone()
                return Member(
                    id=row[0],
                    phone_hash=row[1],
                    display_name=row[2],
                    preferred_language=row[3],
                    knowledge_level=row[4],
                    sacco_id=row[5],
                    is_demo=row[6],
                    created_at=row[7],
                    updated_at=row[8],
                )
        except Exception:
            logger.exception("Failed to create or get demo member in DB")
            return Member(
                id=demo_id,
                phone_hash=phone_hash,
                display_name=display_name,
                preferred_language="en",
                knowledge_level="beginner",
                sacco_id=sacco_id,
                is_demo=True,
            )

    @staticmethod
    def get_accounts(member_id: str) -> list[MemberAccount]:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT id, member_id, account_type, account_name, "
                    "balance, currency, is_demo, updated_at "
                    "FROM member_accounts WHERE member_id = %s",
                    (member_id,),
                )
                return [
                    MemberAccount(
                        id=row[0],
                        member_id=row[1],
                        account_type=row[2],
                        account_name=row[3],
                        balance=float(row[4]),
                        currency=row[5],
                        is_demo=row[6],
                        updated_at=row[7],
                    )
                    for row in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to fetch accounts for member %s", member_id)
            return []

    @staticmethod
    def get_loans(member_id: str) -> list[MemberLoan]:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT id, member_id, loan_type, principal, balance_remaining, "
                    "monthly_instalment, interest_rate, term_months, months_paid, "
                    "status, currency, is_demo, disbursed_at, updated_at "
                    "FROM member_loans WHERE member_id = %s",
                    (member_id,),
                )
                return [
                    MemberLoan(
                        id=row[0],
                        member_id=row[1],
                        loan_type=row[2],
                        principal=float(row[3]),
                        balance_remaining=float(row[4]),
                        monthly_instalment=float(row[5]),
                        interest_rate=float(row[6]),
                        term_months=row[7],
                        months_paid=row[8],
                        status=row[9],
                        currency=row[10],
                        is_demo=row[11],
                        disbursed_at=row[12],
                        updated_at=row[13],
                    )
                    for row in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to fetch loans for member %s", member_id)
            return []
