from enum import Enum

from typing import Literal

from pydantic import BaseModel, Field


class Intent(str, Enum):
    GREETING = "greeting"
    FINANCIAL_EDUCATION = "financial_education"
    SACCO_INFORMATION = "sacco_information"
    GOAL_MANAGEMENT = "goal_management"
    HUMAN_SUPPORT = "human_support"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["en", "sw", "unknown"]

    @classmethod
    def fallback(cls) -> "IntentResult":
        return cls(intent=Intent.UNKNOWN, confidence=0.0, language="unknown")