"""Format member-data snapshots into WhatsApp-friendly plain text.

Design rules (matching RAG output constraints):
- No asterisks, no markdown bold/italic, no em dashes
- Use KSh formatting with thousands-comma separators
- Short, direct sentences
- Optional "(demo data)" label in demo mode
"""

from app.schemas.member import MemberDataResponse


def _ksh(amount: float) -> str:
    """Format a monetary amount as 'KSh 32,450'."""
    if amount == int(amount):
        return f"KSh {int(amount):,}"
    return f"KSh {amount:,.2f}"


def format_full_snapshot(snapshot: MemberDataResponse, *, demo_label: bool = True) -> str:
    """Render a complete member snapshot as WhatsApp-friendly text."""
    lines: list[str] = []

    # Greeting with member name
    lines.append(f"Hello {snapshot.profile.display_name}!")
    lines.append("")

    # Accounts
    if snapshot.accounts:
        for acct in snapshot.accounts:
            lines.append(f"Your {acct.account_name.lower()}: {_ksh(acct.balance)}.")
        lines.append("")

    # Loans
    active_loans = [lo for lo in snapshot.loans if lo.status == "active"]
    if active_loans:
        if len(active_loans) == 1:
            lo = active_loans[0]
            lines.append(
                f"You have 1 active {lo.loan_type} loan: "
                f"{_ksh(lo.balance_remaining)} remaining, "
                f"{_ksh(lo.monthly_instalment)}/month."
            )
        else:
            lines.append(f"You have {len(active_loans)} active loans:")
            for lo in active_loans:
                lines.append(
                    f"- {lo.loan_type.replace('_', ' ').title()} loan: "
                    f"{_ksh(lo.balance_remaining)} remaining, "
                    f"{_ksh(lo.monthly_instalment)}/month."
                )
    elif snapshot.loans:
        lines.append("You have no active loans.")
    else:
        lines.append("You have no loans on record.")

    if demo_label:
        lines.append("")
        lines.append("(demo data)")

    return "\n".join(lines)


def format_balance_response(snapshot: MemberDataResponse, *, demo_label: bool = True) -> str:
    """Render only account balances."""
    lines: list[str] = []
    if snapshot.accounts:
        for acct in snapshot.accounts:
            lines.append(f"Your {acct.account_name.lower()}: {_ksh(acct.balance)}.")
    else:
        lines.append("I don't have account information available right now.")

    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


def format_loan_response(snapshot: MemberDataResponse, *, demo_label: bool = True) -> str:
    """Render only loan information."""
    lines: list[str] = []
    active_loans = [lo for lo in snapshot.loans if lo.status == "active"]
    if active_loans:
        for lo in active_loans:
            lines.append(
                f"Your {lo.loan_type.replace('_', ' ')} loan: "
                f"{_ksh(lo.balance_remaining)} remaining out of {_ksh(lo.principal)}. "
                f"Monthly instalment: {_ksh(lo.monthly_instalment)}. "
                f"Months paid: {lo.months_paid}/{lo.term_months}."
            )
    elif snapshot.loans:
        lines.append("You have no active loans.")
    else:
        lines.append("You have no loans on record.")

    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sub-question detection helpers
# ---------------------------------------------------------------------------
_BALANCE_KEYWORDS = {"balance", "savings", "shares", "deposit", "pesa", "akiba"}
_LOAN_KEYWORDS = {
    "loan", "owe", "repay", "repayment", "instalment", "installment",
    "deni", "mkopo", "payment", "payments", "pay", "due", "kulipa",
}


def detect_sub_question(query: str) -> str:
    """Return 'balance', 'loan', or 'full' based on the user's query."""
    lower = query.lower()
    has_balance = any(kw in lower for kw in _BALANCE_KEYWORDS)
    has_loan = any(kw in lower for kw in _LOAN_KEYWORDS)

    if has_balance and not has_loan:
        return "balance"
    if has_loan and not has_balance:
        return "loan"
    return "full"


def format_member_response(
    snapshot: MemberDataResponse,
    query: str,
    *,
    demo_label: bool = True,
) -> str:
    """Choose the most appropriate format based on the user's question."""
    sub = detect_sub_question(query)
    if sub == "balance":
        return format_balance_response(snapshot, demo_label=demo_label)
    if sub == "loan":
        return format_loan_response(snapshot, demo_label=demo_label)
    return format_full_snapshot(snapshot, demo_label=demo_label)
