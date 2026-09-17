"""Member data service — resolves identity and aggregates financial data.

This is the abstraction layer between repositories and the conversation
orchestrator.  It hashes phone numbers, queries the member repository,
and assembles combined snapshots.  The service is independent of the
transport layer (WhatsApp, API, etc.).
"""

import logging

from typing import Any, Optional

from app.database.member_repository import MemberRepository, _hash_phone
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.models.member import Member
from app.schemas.member import (
    AccountSummary,
    LoanSummary,
    MemberDataResponse,
    MemberProfile,
)
from app.services.members.sacco_adapter import (
    BaseSaccoAdapter,
    DatabaseSaccoAdapter,
    LoanRecord,
    SavingsBalance,
    TransactionRecord,
    ChangeRequestRecord,
)

logger = logging.getLogger(__name__)


class MemberDataService:
    """Aggregate member identity + financial data lookups with pluggable SACCO adapters."""

    def __init__(
        self,
        repository: MemberRepository | InMemoryMemberRepository | None = None,
        adapter: Optional[BaseSaccoAdapter] = None,
    ) -> None:
        self._repo = repository or MemberRepository()
        self._adapter = adapter or DatabaseSaccoAdapter(repository=self._repo)

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    def resolve_member(self, phone_number: str) -> MemberProfile | None:
        """Resolve a WhatsApp phone number to a member profile.

        Returns ``None`` when the number is not associated with any member.
        """
        member = self._repo.get_by_phone(phone_number)
        if member is None:
            logger.info("Member not found for phone (hash=%s…)", _hash_phone(phone_number)[:8])
            return None
        return MemberProfile(
            id=member.id,
            display_name=member.display_name,
            preferred_language=member.preferred_language,
            knowledge_level=member.knowledge_level,
            sacco_id=member.sacco_id,
        )

    def get_member_profile(self, member_id: str) -> MemberProfile | None:
        """Resolve a member ID directly to a member profile.

        Returns ``None`` when the ID is not found.
        """
        member = self._repo.get_by_id(member_id)
        if member is None:
            return None
        return MemberProfile(
            id=member.id,
            display_name=member.display_name,
            preferred_language=member.preferred_language,
            knowledge_level=member.knowledge_level,
            sacco_id=member.sacco_id,
        )

    def get_or_create_demo_member(
        self,
        phone_number: str,
        display_name: str = "Member",
        sacco_id: str | None = None,
    ) -> MemberProfile:
        """Ensure demo member exists in the repository and return MemberProfile."""
        from app.config.settings import settings
        sid = sacco_id or settings.DEFAULT_SACCO_ID
        if hasattr(self._repo, "create_or_get_demo_member"):
            member = self._repo.create_or_get_demo_member(phone_number, display_name=display_name, sacco_id=sid)
            return MemberProfile(
                id=member.id,
                display_name=member.display_name,
                preferred_language=member.preferred_language,
                knowledge_level=member.knowledge_level,
                sacco_id=member.sacco_id,
            )
        phone_hash = _hash_phone(phone_number)
        return MemberProfile(
            id=f"demo_{phone_hash[:8]}",
            display_name=display_name,
            preferred_language="en",
            knowledge_level="beginner",
            sacco_id=sid,
        )

    # ------------------------------------------------------------------
    # Financial data
    # ------------------------------------------------------------------

    def get_account_summary(self, member_id: str) -> list[AccountSummary]:
        """Return account summaries for a verified member."""
        accounts = self._repo.get_accounts(member_id)
        return [
            AccountSummary(
                account_type=a.account_type,
                account_name=a.account_name,
                balance=a.balance,
                currency=a.currency,
            )
            for a in accounts
        ]

    def get_loan_summary(self, member_id: str) -> list[LoanSummary]:
        """Return loan summaries for a verified member."""
        loans = self._repo.get_loans(member_id)
        return [
            LoanSummary(
                loan_type=lo.loan_type,
                principal=lo.principal,
                balance_remaining=lo.balance_remaining,
                monthly_instalment=lo.monthly_instalment,
                interest_rate=lo.interest_rate,
                term_months=lo.term_months,
                months_paid=lo.months_paid,
                status=lo.status,
                currency=lo.currency,
            )
            for lo in loans
        ]

    # ------------------------------------------------------------------
    # Combined snapshot
    # ------------------------------------------------------------------

    def get_member_snapshot(self, phone_number: str) -> MemberDataResponse | None:
        """Return profile + accounts + loans in a single call.

        Returns ``None`` when the phone number does not match any member.
        """
        profile = self.resolve_member(phone_number)
        if profile is None:
            return None
        accounts = self.get_account_summary(profile.id)
        loans = self.get_loan_summary(profile.id)
        return MemberDataResponse(profile=profile, accounts=accounts, loans=loans)

    # ------------------------------------------------------------------
    # Data Minimization & SACCO Adapter Delegation (System 12)
    # ------------------------------------------------------------------

    def get_savings_balance(self, member_id: str, sacco_id: str = "demo_sacco") -> Optional[SavingsBalance]:
        """Data-minimized savings balance lookup."""
        return self._adapter.get_savings_balance(member_id, sacco_id)

    def get_all_balances(self, member_id: str, sacco_id: str = "demo_sacco") -> list[SavingsBalance]:
        """Retrieve all member account balances."""
        return self._adapter.get_all_balances(member_id, sacco_id)

    def get_loans(self, member_id: str, sacco_id: str = "demo_sacco") -> list[LoanRecord]:
        """Data-minimized loan obligations lookup."""
        return self._adapter.get_loans(member_id, sacco_id)

    def get_transactions(self, member_id: str, sacco_id: str = "demo_sacco", limit: int = 5) -> list[TransactionRecord]:
        """Data-minimized transaction history lookup."""
        return self._adapter.get_transactions(member_id, sacco_id, limit=limit)

    def request_account_change(
        self,
        member_id: str,
        sacco_id: str,
        change_type: str,
        payload: dict[str, Any],
    ) -> ChangeRequestRecord:
        """Governed write operation creating a pending change request."""
        return self._adapter.submit_change_request(member_id, sacco_id, change_type, payload)
