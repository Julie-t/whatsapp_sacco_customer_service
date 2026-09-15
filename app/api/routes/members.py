"""Internal admin/debug API for member data inspection.

These endpoints are NOT exposed to WhatsApp members — they are
intended for developer debugging and internal tooling only.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.member import (
    AccountSummary,
    LoanSummary,
    MemberDataResponse,
    MemberProfile,
)
from app.services.members.member_service import MemberDataService

router = APIRouter(prefix="/members", tags=["members"])

_service: MemberDataService | None = None


def _get_service() -> MemberDataService:
    global _service
    if _service is None:
        _service = MemberDataService()
    return _service


@router.get("/{member_id}", response_model=MemberProfile)
def get_member_profile(member_id: str):
    """Look up a member profile by ID."""
    from app.database.member_repository import MemberRepository

    repo = MemberRepository()
    member = repo.get_by_id(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return MemberProfile(
        id=member.id,
        display_name=member.display_name,
        preferred_language=member.preferred_language,
        knowledge_level=member.knowledge_level,
        sacco_id=member.sacco_id,
    )


@router.get("/{member_id}/accounts", response_model=list[AccountSummary])
def get_member_accounts(member_id: str):
    """Return account summaries for a member."""
    service = _get_service()
    accounts = service.get_account_summary(member_id)
    if not accounts:
        # Verify the member exists first
        from app.database.member_repository import MemberRepository

        if MemberRepository().get_by_id(member_id) is None:
            raise HTTPException(status_code=404, detail="Member not found")
    return accounts


@router.get("/{member_id}/loans", response_model=list[LoanSummary])
def get_member_loans(member_id: str):
    """Return loan summaries for a member."""
    service = _get_service()
    loans = service.get_loan_summary(member_id)
    if not loans:
        from app.database.member_repository import MemberRepository

        if MemberRepository().get_by_id(member_id) is None:
            raise HTTPException(status_code=404, detail="Member not found")
    return loans


@router.get("/{member_id}/snapshot", response_model=MemberDataResponse)
def get_member_snapshot(member_id: str):
    """Return the full member data snapshot (profile + accounts + loans)."""
    from app.database.member_repository import MemberRepository

    repo = MemberRepository()
    member = repo.get_by_id(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    service = _get_service()
    return MemberDataResponse(
        profile=MemberProfile(
            id=member.id,
            display_name=member.display_name,
            preferred_language=member.preferred_language,
            knowledge_level=member.knowledge_level,
            sacco_id=member.sacco_id,
        ),
        accounts=service.get_account_summary(member_id),
        loans=service.get_loan_summary(member_id),
    )
