"""Typed models for evaluation datasets and execution results."""

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    id: str
    question: str = Field(min_length=1)
    language: Literal["en", "sw", "mixed"] = "en"
    sacco_id: str = "demo_sacco"
    expected_behavior: Literal[
        "answer", "clarification", "knowledge_gap", "guardrail", "human_escalation", "provider_failure"
    ]
    expected_source: str | None = None
    expected_fallback: str | None = None
    expected_claims: list[str] = Field(default_factory=list)
    notes: str = ""


class ClaimResult(BaseModel):
    claim: str
    supported: bool
    evidence: list[str] = Field(default_factory=list)


class MetricResult(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    details: dict[str, object] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    case_id: str
    question: str
    expected_behavior: str
    actual_behavior: str | None = None
    answer: str | None = None
    reformulated_query: str | None = None
    retrieval: dict[str, object] = Field(default_factory=dict)
    answerability: dict[str, object] = Field(default_factory=dict)
    routing: dict[str, object] = Field(default_factory=dict)
    groundedness: MetricResult | None = None
    relevance: MetricResult | None = None
    language: MetricResult | None = None
    verification: dict[str, object] = Field(default_factory=dict)
    fallback: MetricResult | None = None
    provider_failure_type: str | None = None
    passed: bool = False
    failure_type: str | None = None
    error: str | None = None
