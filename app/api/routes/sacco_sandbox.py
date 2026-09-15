"""SACCO Integration Sandbox API (System 12).

Simulates external core banking system / ERP REST API endpoints.
Provides mock fixtures for offline testing and onboarding validation.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/sandbox/sacco", tags=["sacco_sandbox"])

# In-memory sandbox fixture data
SANDBOX_MEMBERS: dict[str, dict[str, Any]] = {
    "mem_001": {
        "id": "mem_001",
        "display_name": "Edna Maina",
        "membership_status": "active",
        "sacco_id": "demo_sacco",
        "preferred_language": "mixed",
        "knowledge_level": "beginner",
        "balance": 32450.0,
        "available_balance": 32450.0,
        "currency": "KSh",
        "account_number": "SAV-001092",
        "loans": [
            {
                "loan_id": "LN-2024-001",
                "loan_type": "development",
                "principal": 200000.0,
                "balance_remaining": 125000.0,
                "monthly_instalment": 4500.0,
                "status": "active",
                "currency": "KSh",
            }
        ],
        "transactions": [
            {
                "transaction_id": "TXN-001-99",
                "account_type": "savings",
                "transaction_type": "deposit",
                "amount": 5000.0,
                "balance_after": 32450.0,
                "timestamp": "2026-09-01T10:15:00Z",
                "description": "M-Pesa Checkoff Contribution",
            },
            {
                "transaction_id": "TXN-001-98",
                "account_type": "savings",
                "transaction_type": "deposit",
                "amount": 5000.0,
                "balance_after": 27450.0,
                "timestamp": "2026-08-01T09:30:00Z",
                "description": "M-Pesa Checkoff Contribution",
            },
        ],
    },
    "mem_002": {
        "id": "mem_002",
        "display_name": "James Ochieng",
        "membership_status": "active",
        "sacco_id": "demo_sacco",
        "preferred_language": "en",
        "knowledge_level": "intermediate",
        "balance": 185000.0,
        "available_balance": 180000.0,
        "currency": "KSh",
        "account_number": "SAV-002844",
        "loans": [],
        "transactions": [],
    },
}


class SandboxChangeRequest(BaseModel):
    change_type: str
    payload: dict[str, Any]


@router.get("/{sacco_id}/members/{member_id}")
def get_sandbox_member(sacco_id: str, member_id: str):
    """Fetch member profile from sandbox."""
    if sacco_id != "demo_sacco":
        raise HTTPException(status_code=403, detail="Tenant access denied in sandbox")
    member = SANDBOX_MEMBERS.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in sandbox")
    return {
        "id": member["id"],
        "display_name": member["display_name"],
        "membership_status": member["membership_status"],
        "sacco_id": member["sacco_id"],
        "preferred_language": member["preferred_language"],
        "knowledge_level": member["knowledge_level"],
    }


@router.get("/{sacco_id}/members/{member_id}/balance")
def get_sandbox_balance(sacco_id: str, member_id: str):
    """Fetch savings/deposit balance from sandbox."""
    if sacco_id != "demo_sacco":
        raise HTTPException(status_code=403, detail="Tenant access denied in sandbox")
    member = SANDBOX_MEMBERS.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in sandbox")
    return {
        "account_number": member["account_number"],
        "account_type": "savings",
        "balance": member["balance"],
        "available_balance": member["available_balance"],
        "currency": member["currency"],
    }


@router.get("/{sacco_id}/members/{member_id}/loans")
def get_sandbox_loans(sacco_id: str, member_id: str):
    """Fetch loan obligations from sandbox."""
    if sacco_id != "demo_sacco":
        raise HTTPException(status_code=403, detail="Tenant access denied in sandbox")
    member = SANDBOX_MEMBERS.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in sandbox")
    return member["loans"]


@router.get("/{sacco_id}/members/{member_id}/transactions")
def get_sandbox_transactions(sacco_id: str, member_id: str, limit: int = Query(default=5, ge=1, le=20)):
    """Fetch transactions from sandbox."""
    if sacco_id != "demo_sacco":
        raise HTTPException(status_code=403, detail="Tenant access denied in sandbox")
    member = SANDBOX_MEMBERS.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in sandbox")
    return member["transactions"][:limit]


@router.post("/{sacco_id}/members/{member_id}/change-requests")
def submit_sandbox_change_request(sacco_id: str, member_id: str, body: SandboxChangeRequest):
    """Log governed change request."""
    if sacco_id != "demo_sacco":
        raise HTTPException(status_code=403, detail="Tenant access denied in sandbox")
    member = SANDBOX_MEMBERS.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in sandbox")
    return {
        "id": f"sandbox_req_{member_id[:6]}_{int(datetime.now(timezone.utc).timestamp())}",
        "member_id": member_id,
        "sacco_id": sacco_id,
        "change_type": body.change_type,
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Change request received by SACCO core banking sandbox and queued for review.",
    }
