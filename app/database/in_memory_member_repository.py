"""In-memory member repository for unit tests."""

from app.database.member_repository import _hash_phone
from app.models.member import Member, MemberAccount, MemberLoan


class InMemoryMemberRepository:
    """Dict-backed member repository for testing without PostgreSQL."""

    def __init__(self) -> None:
        self._members: dict[str, Member] = {}
        self._phone_index: dict[str, str] = {}  # phone_hash -> member_id
        self._accounts: dict[str, list[MemberAccount]] = {}
        self._loans: dict[str, list[MemberLoan]] = {}

    def add_member(
        self,
        member: Member,
        phone_number: str,
        accounts: list[MemberAccount] | None = None,
        loans: list[MemberLoan] | None = None,
    ) -> None:
        """Seed a member for testing."""
        phone_hash = _hash_phone(phone_number)
        member.phone_hash = phone_hash
        self._members[member.id] = member
        self._phone_index[phone_hash] = member.id
        if accounts:
            self._accounts[member.id] = list(accounts)
        if loans:
            self._loans[member.id] = list(loans)

    def get_by_phone(self, phone_number: str) -> Member | None:
        phone_hash = _hash_phone(phone_number)
        member_id = self._phone_index.get(phone_hash)
        if member_id is None:
            raw = phone_number.strip().replace(" ", "")
            alt = raw[len("whatsapp:"):] if raw.startswith("whatsapp:") else f"whatsapp:{raw}"
            member_id = self._phone_index.get(_hash_phone(alt))
        if member_id is None:
            return None
        return self._members.get(member_id)

    def get_by_id(self, member_id: str) -> Member | None:
        return self._members.get(member_id)

    def get_accounts(self, member_id: str) -> list[MemberAccount]:
        return list(self._accounts.get(member_id, []))

    def get_loans(self, member_id: str) -> list[MemberLoan]:
        return list(self._loans.get(member_id, []))

    def create_or_get_demo_member(
        self,
        phone_number: str,
        display_name: str = "Member",
        sacco_id: str = "demo_sacco",
    ) -> Member:
        phone_hash = _hash_phone(phone_number)
        if phone_hash in self._phone_index:
            return self._members[self._phone_index[phone_hash]]
        demo_id = f"demo_{phone_hash[:8]}"
        member = Member(
            id=demo_id,
            phone_hash=phone_hash,
            display_name=display_name,
            preferred_language="en",
            knowledge_level="beginner",
            sacco_id=sacco_id,
            is_demo=True,
        )
        self.add_member(member, phone_number)
        return member
