"""Member Data Grounding Service (System 12).

Provides dual-boundary grounding validation: ensures that any AI-generated response
mentioning member balances, loans, or repayments strictly matches authoritative SACCO records.
Detects and blocks hallucinated or altered financial numbers (MEMBER DATA MISMATCH).
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemberGroundingResult:
    is_grounded: bool
    hallucinated_figures: list[float] = field(default_factory=list)
    authoritative_figures: list[float] = field(default_factory=list)
    fallback_message: Optional[str] = None
    audit_notes: str = ""


class MemberDataGroundingService:
    """Validates generated text against authoritative financial records."""

    # Matches numbers formatted as currency (e.g., KSh 32,450, KES 125,000, 32,450.00)
    CURRENCY_REGEX = re.compile(
        r"(?:(?:KSh|KES)\.?\s*|(?<=\s))([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|\b[0-9]{4,}\b)",
        re.IGNORECASE,
    )

    def extract_monetary_values(self, text: str) -> list[float]:
        """Parse all potential currency/numerical amounts from generated text."""
        values: list[float] = []
        for match in self.CURRENCY_REGEX.finditer(text):
            raw = match.group(1).replace(",", "")
            try:
                val = float(raw)
                # Ignore small numbers that are likely years, counts, or small dates (e.g. 2026, 12, 1)
                if val >= 100.0:
                    values.append(val)
            except ValueError:
                continue
        return values

    def extract_authoritative_numbers(self, authoritative_context: dict[str, Any]) -> set[float]:
        """Extract all valid numbers from authoritative records (profile, accounts, loans, goals)."""
        valid_nums: set[float] = set()

        def _walk(obj: Any):
            if isinstance(obj, (int, float)):
                valid_nums.add(round(float(obj), 2))
                # Also add integer representation
                valid_nums.add(float(int(obj)))
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    _walk(item)
            elif hasattr(obj, "__dict__"):
                for v in vars(obj).values():
                    _walk(v)

        _walk(authoritative_context)
        return valid_nums

    def verify_response(
        self,
        generated_text: str,
        authoritative_context: dict[str, Any],
        fallback_template: Optional[str] = None,
    ) -> MemberGroundingResult:
        """Verify that every monetary figure in the generated text exists in the authoritative context."""
        claimed_numbers = self.extract_monetary_values(generated_text)
        authoritative_numbers = self.extract_authoritative_numbers(authoritative_context)

        mismatches: list[float] = []
        for num in claimed_numbers:
            # Check direct match with tolerance of 0.01 for rounding
            matched = any(abs(num - auth) < 0.05 for auth in authoritative_numbers)
            if not matched:
                mismatches.append(num)

        if mismatches:
            logger.warning(
                "MEMBER DATA MISMATCH: Generated text claimed %s, but authoritative values are %s",
                mismatches,
                sorted(authoritative_numbers),
            )
            return MemberGroundingResult(
                is_grounded=False,
                hallucinated_figures=mismatches,
                authoritative_figures=sorted(authoritative_numbers),
                fallback_message=fallback_template,
                audit_notes=f"Blocked hallucinated figures: {mismatches}",
            )

        return MemberGroundingResult(
            is_grounded=True,
            authoritative_figures=sorted(authoritative_numbers),
            audit_notes="All member numerical figures grounded in authoritative source.",
        )
