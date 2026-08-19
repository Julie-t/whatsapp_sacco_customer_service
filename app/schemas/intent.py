from typing import Literal

from pydantic import BaseModel


class RequestTriageResult(BaseModel):
    language: Literal["en", "sw", "mixed"]
    needs_member_data: bool
    likely_needs_human: bool
    reasoning: str

    @classmethod
    def fallback(cls) -> "RequestTriageResult":
        return cls(
            language="mixed",
            needs_member_data=False,
            likely_needs_human=True,
            reasoning="The request could not be reliably classified for routing.",
        )