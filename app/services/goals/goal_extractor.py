"""Extract structured goal parameters from natural language user messages."""

import json
import logging
import re
from datetime import date
from typing import Optional

from app.ai.llm import LLM
from app.models.goal import GoalType
from app.schemas.goal import GoalExtractionResult
from app.services.goals.goal_calculator import add_months

logger = logging.getLogger(__name__)

GOAL_EXTRACTION_PROMPT = """You are a financial goal extractor for a Kenyan SACCO companion.
Given the user's message (and recent conversation context), extract the financial goal details in JSON only:
{
  "goal_type": "education" | "emergency_fund" | "retirement" | "asset_purchase" | "general_savings" | "business" | "custom" | null,
  "name": string | null,
  "target_amount": number | null,
  "timeline_months": number | null,
  "current_amount": number | null,
  "monthly_contribution": number | null,
  "is_scenario_query": boolean,
  "proposed_scenario_amount": number | null,
  "secondary_scenario_amount": number | null,
  "is_progress_inquiry": boolean,
  "is_balance_update": boolean
}

Rules:
- Amounts like "300k", "300,000", "KSh 240,000", "raise 300,000" should be numbers: 300000, 240000.
- Timelines like "2 years" -> 24, "18 months" -> 18, "1 year" -> 12, "next year" -> 12, "by next year" -> 12, "end of year" -> remaining months.
- "What if I save 15k instead?" or "I can manage KSh 10,000 every month. Will that be enough?" -> is_scenario_query=true, proposed_scenario_amount=10000 (or 15000).
- "Which one is better for me, saving 10,000 or 15,000?" or "Compare saving 10k vs 15k" -> is_scenario_query=true, proposed_scenario_amount=10000, secondary_scenario_amount=15000, target_amount=null.
- "What is my goal progress?" or "How is my school fees goal doing?" -> is_progress_inquiry=true.
- "I have already saved KSh 80,000" or "I have 80k already" -> is_balance_update=true, current_amount=80000.
- Do not extract target_amount or timeline_months from conversation context if the user's current message is only asking a follow-up question or asking about products. Amounts must be stated or confirmed by the user in the current turn.
- Do not invent numbers. If not mentioned, set to null.
- Output JSON ONLY. No explanation.
"""


def _parse_amount(text: str) -> Optional[float]:
    """Parse amounts like 'KSh 300,000', '300k', '240000', 'raise 300,000' (ignoring small integers followed by time units)."""
    # Pattern for 300k / 300K
    match_k = re.search(r"\b(\d+(?:\.\d+)?)\s*[kK]\b", text)
    if match_k:
        return float(match_k.group(1)) * 1000.0

    # Pattern for 1.5m / 2 million
    match_m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:million|m)\b", text, re.IGNORECASE)
    if match_m:
        sub_after = text[match_m.end():match_m.end()+6].lower()
        if not any(unit in sub_after for unit in ("onth", "eter")):
            return float(match_m.group(1)) * 1000000.0

    # Pattern with explicit currency: KSh 300,000 / KES 20000
    match_curr = re.search(r"(?:ksh|kes)\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match_curr:
        clean = match_curr.group(1).replace(",", "")
        try:
            val = float(clean)
            if val > 0:
                return val
        except ValueError:
            pass

    # Pattern with action verbs: raise 300,000 / save 250000 / changa 50000
    match_verb = re.search(r"\b(?:raise|changa|save|collect|target\s+of)\s*(?:ksh|kes)?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{3,}(?:\.\d+)?)", text, re.IGNORECASE)
    if match_verb:
        clean = match_verb.group(1).replace(",", "")
        try:
            val = float(clean)
            if val >= 100:
                return val
        except ValueError:
            pass

    # Pattern for numbers with comma grouping: 240,000 or large numbers >= 1000 not followed by year/month/day
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{3,}(?:\.\d+)?)\b", text):
        clean = m.group(1).replace(",", "")
        # Check that it's not followed by a time unit (e.g. 2028 or 24 months)
        sub_after = text[m.end():m.end()+15].lower()
        if any(unit in sub_after for unit in ("year", "yr", "month", "mo", "week", "day", "miaka", "miezi")):
            continue
        # Ignore plausible 4-digit calendar years unless explicitly prefixed by currency
        if re.match(r"^20\d\d$", clean):
            sub_before = text[max(0, m.start()-15):m.start()].lower()
            if any(p in sub_before for p in ("by", "in", "year", "mwaka", "september", "december", "january", "february", "march", "april", "may", "june", "july", "august", "october", "november", "sep", "dec", "nov", "oct", "aug", "jul", "jun", "apr", "mar", "feb", "jan")):
                continue
        try:
            val = float(clean)
            if val >= 100:  # Minimum realistic goal amount
                return val
        except ValueError:
            pass
    return None


def _parse_all_amounts(text: str) -> list[float]:
    """Extract all distinct monetary amounts from a string in order of appearance."""
    results: list[float] = []
    # Explicit currency: KSh 10,000 / KES 15000
    for m in re.finditer(r"(?:ksh|kes)\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", text, re.IGNORECASE):
        try:
            val = float(m.group(1).replace(",", ""))
            if val >= 100 and val not in results:
                results.append(val)
        except ValueError:
            pass

    # Numbers with commas or numbers >= 1000
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{3,}(?:\.\d+)?)\b", text):
        clean = m.group(1).replace(",", "")
        if re.match(r"^20\d\d$", clean):
            sub_before = text[max(0, m.start()-15):m.start()].lower()
            if any(p in sub_before for p in ("by", "in", "year", "mwaka", "september", "december", "january", "february", "march", "april", "may", "june", "july", "august", "october", "november", "sep", "dec", "nov", "oct", "aug", "jul", "jun", "apr", "mar", "feb", "jan")):
                continue
        sub_after = text[m.end():m.end()+15].lower()
        if any(unit in sub_after for unit in ("year", "yr", "month", "mo", "week", "day", "miaka", "miezi")):
            continue
        try:
            val = float(clean)
            if val >= 100 and val not in results:
                results.append(val)
        except ValueError:
            pass
    return results


def _parse_months(text: str) -> Optional[int]:
    """Parse timeline expressions like '2 years', '18 months', 'by next year', 'end of year', 'by September 2027', 'miaka 3'."""
    # Idiomatic Kenyan English & Swahili relative timelines:
    # "next year", "by next year", "in a year", "within a year", "mwaka ujao", "mwaka kesho"
    if re.search(r"\b(?:by\s+)?(?:next\s+year|in\s+a\s+year|within\s+a\s+year|mwaka\s+(?:ujao|kesho))\b", text, re.IGNORECASE):
        return 12

    # "end of year", "by end of year", "this year", "mwisho wa mwaka"
    if re.search(r"\b(?:by\s+)?(?:end\s+of\s+(?:this\s+)?year|by\s+year\s+end|year\s+end|this\s+year|mwisho\s+wa\s+mwaka)\b", text, re.IGNORECASE):
        remaining = 12 - date.today().month
        return max(1, remaining)

    # "half a year", "half year", "nusu mwaka"
    if re.search(r"\b(?:half\s+(?:a\s+)?year|nusu\s+mwaka)\b", text, re.IGNORECASE):
        return 6

    # "next month", "in a month", "within a month", "mwezi ujao"
    if re.search(r"\b(?:by\s+)?(?:next\s+month|in\s+a\s+month|within\s+a\s+month|mwezi\s+ujao)\b", text, re.IGNORECASE):
        return 1

    # Explicit calendar month and year: e.g. "by September 2027", "September 2027", "in August 2026"
    months_map = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    month_names_regex = "|".join(months_map.keys())
    match_month_yr = re.search(
        rf"\b(?:by\s+|in\s+)?({month_names_regex})\s+(\d{{4}})\b",
        text,
        re.IGNORECASE,
    )
    if match_month_yr:
        m_name = match_month_yr.group(1).lower()
        target_month = months_map[m_name]
        target_year = int(match_month_yr.group(2))
        today = date.today()
        diff_months = (target_year - today.year) * 12 + (target_month - today.month)
        if diff_months > 0:
            return diff_months

    # Explicit year only: e.g. "by 2027", "in 2028"
    match_yr_only = re.search(r"\b(?:by\s+|in\s+)(20\d\d)\b", text, re.IGNORECASE)
    if match_yr_only:
        target_year = int(match_yr_only.group(1))
        today = date.today()
        diff_months = (target_year - today.year) * 12 + (12 - today.month)
        if diff_months > 0:
            return diff_months

    # Years: '2 years', '2 yrs', 'miaka 2', '2 miaka'
    match_yr = re.search(r"\b(?:miaka\s+(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:years?|yrs?|miaka))\b", text, re.IGNORECASE)
    if match_yr:
        num = match_yr.group(1) or match_yr.group(2)
        return int(float(num) * 12)

    # Months: '18 months', '18 mos', 'miezi 6', '6 miezi'
    match_mo = re.search(r"\b(?:miezi\s+(\d+)|(\d+)\s*(?:months?|mos?|miezi))\b", text, re.IGNORECASE)
    if match_mo:
        num = match_mo.group(1) or match_mo.group(2)
        return int(num)
    return None


def _detect_goal_type(text: str) -> tuple[GoalType, str]:
    lower = text.lower()
    if any(w in lower for w in ("school", "university", "college", "fees", "education", "shule", "masomo")):
        return GoalType.EDUCATION, "Education / School Fees"
    if any(w in lower for w in ("emergency", "buffer", "contingency", "dharura")):
        return GoalType.EMERGENCY_FUND, "Emergency Fund"
    if any(w in lower for w in ("retire", "pension", "old age", "ustaafu")):
        return GoalType.RETIREMENT, "Retirement"
    if any(w in lower for w in ("land", "plot", "car", "house", "building", "asset", "gari", "nyumba", "shamba")):
        return GoalType.ASSET_PURCHASE, "Asset Purchase"
    if any(w in lower for w in ("business", "shop", "duka", "inventory", "stock", "biashara", "expand", "kukuza")):
        return GoalType.BUSINESS, "Business Growth"
    return GoalType.GENERAL_SAVINGS, "Savings Goal"


class GoalExtractor:
    """Extracts goal intent and parameters using fast regex heuristics with LLM fallback."""

    def __init__(self, llm: Optional[LLM] = None):
        self.llm = llm

    def extract_heuristic(self, message: str) -> GoalExtractionResult:
        """Fast regex heuristic extraction without calling LLM."""
        lower = message.lower()

        # Check for starting balance / already saved statement
        is_balance_update = any(
            p in lower for p in (
                "already saved",
                "have already saved",
                "have saved",
                "currently saved",
                "current savings",
                "already have",
                "currently have",
                "tayari nina",
                "nimeshaweka",
                "nimehifadhi",
                "saved already",
            )
        )
        if is_balance_update:
            amount = _parse_amount(message)
            if amount:
                return GoalExtractionResult(
                    is_balance_update=True,
                    current_amount=amount,
                )

        is_comparison = bool(re.search(
            r"\b(which\s+one\s+is\s+better|which\s+is\s+better|better\s+for\s+me|should\s+i\s+save|"
            r"compare|versus|\bvs\b|between\s+\d+.*and\s+\d+)\b",
            lower,
        ))
        is_scenario = (
            is_comparison
            or any(p in lower for p in ("what if", "badala ya", "instead of", "if i save"))
            or (any(p in lower for p in ("manage", "afford", "can i do", "what about", "will that be enough", "is that enough", "will it be enough")) and any(u in lower for u in ("month", "monthly", "mwezi", "kila mwezi", "every month", "per month", "each month")))
        )

        if is_scenario:
            amounts = _parse_all_amounts(message)
            opt_a = amounts[0] if len(amounts) > 0 else _parse_amount(message)
            opt_b = amounts[1] if len(amounts) > 1 else None
            return GoalExtractionResult(
                is_scenario_query=True,
                proposed_scenario_amount=opt_a,
                secondary_scenario_amount=opt_b,
                needs_clarification=False,
            )

        is_progress = any(p in lower for p in ("progress", "how much have i saved", "status of my goal", "goal status", "lengo langu linaendeleaje", "how far")) or (
            "status" in lower and "goal" in lower
        )

        if is_progress and not any(w in lower for w in ("want to save", "create", "start a goal", "new goal", "raise", "plan")):
            return GoalExtractionResult(
                is_progress_inquiry=True,
            )

        # Regular contribution / monthly savings statement
        # e.g. "I can normally put aside KSh 10,000 every month, but sometimes business is slow."
        # or "Some months I can save 15,000 and some months only 5,000."
        is_contrib_statement = (
            any(
                p in lower for p in (
                    "put aside",
                    "putting aside",
                    "can put aside",
                    "save every month",
                    "save each month",
                    "save per month",
                    "every month",
                    "per month",
                    "each month",
                    "a month",
                    "monthly",
                    "kila mwezi",
                    "some months",
                    "business is slow",
                    "income fluctuates",
                    "income varies",
                    "irregular",
                )
            )
            and not any(p in lower for p in ("what if", "badala ya", "instead of", "if i save"))
            and not any(w in lower for w in ("want to save", "target of", "raise", "goal of"))
        )
        if is_contrib_statement:
            amount = _parse_amount(message)
            if amount:
                return GoalExtractionResult(
                    monthly_contribution=amount,
                    needs_clarification=False,
                )

        goal_type, default_name = _detect_goal_type(message)
        amount = _parse_amount(message)
        months = _parse_months(message)
        target_date = add_months(date.today(), months) if months else None

        missing = []
        if not amount:
            missing.append("target_amount")
        if not months:
            missing.append("target_date")

        return GoalExtractionResult(
            goal_type=goal_type,
            name=default_name,
            target_amount=amount,
            timeline_months=months,
            target_date=target_date,
            needs_clarification=bool(missing),
            missing_fields=missing,
        )

    async def extract_async(self, message: str, context: Optional[str] = None) -> GoalExtractionResult:
        """Extract using LLM for nuance, falling back to heuristics."""
        if not self.llm:
            return self.extract_heuristic(message)

        try:
            prompt = GOAL_EXTRACTION_PROMPT
            if context:
                prompt += f"\nRecent Context:\n{context}\n"

            raw = await self.llm.generate([
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ])

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                payload = json.loads(match.group(0))
                heuristic_res = self.extract_heuristic(message)

                timeline_months = payload.get("timeline_months") or _parse_months(message)
                target_date = add_months(date.today(), timeline_months) if timeline_months else None

                target_amount = float(payload["target_amount"]) if payload.get("target_amount") else _parse_amount(message)

                missing = []
                if not target_amount:
                    missing.append("target_amount")
                if not timeline_months:
                    missing.append("target_date")

                extracted_type = GoalType(payload["goal_type"]) if payload.get("goal_type") else None
                heuristic_type, heuristic_name = _detect_goal_type(message + (" " + context if context else ""))
                final_type = extracted_type or heuristic_type
                final_name = payload.get("name") or heuristic_name

                is_balance_update = bool(payload.get("is_balance_update")) or heuristic_res.is_balance_update
                if not is_balance_update and any(p in message.lower() for p in ("already saved", "have already saved", "already have", "currently have", "nimeshaweka", "saved already")):
                    is_balance_update = True

                is_scenario_query = bool(payload.get("is_scenario_query")) or heuristic_res.is_scenario_query
                proposed_scenario_amount = float(payload["proposed_scenario_amount"]) if payload.get("proposed_scenario_amount") else None
                sec_scenario_amount = float(payload["secondary_scenario_amount"]) if payload.get("secondary_scenario_amount") else None
                if heuristic_res.is_scenario_query:
                    is_scenario_query = True
                    proposed_scenario_amount = proposed_scenario_amount or heuristic_res.proposed_scenario_amount
                    sec_scenario_amount = sec_scenario_amount or heuristic_res.secondary_scenario_amount
                if not proposed_scenario_amount and is_scenario_query:
                    proposed_scenario_amount = _parse_amount(message)

                # Disambiguation: If user is stating regular monthly contribution/income variability without scenario question phrasing, it is a budget contribution update, NOT a scenario query
                if heuristic_res.monthly_contribution is not None:
                    has_explicit_scenario_verb = any(
                        p in message.lower() for p in (
                            "what if", "badala ya", "instead of", "if i save",
                            "will that be enough", "will it be enough", "is that enough",
                            "which one is better", "which is better", "better for me",
                            "compare", "versus", "vs", "or saving", "suppose", "?"
                        )
                    )
                    if not has_explicit_scenario_verb:
                        is_scenario_query = False
                        proposed_scenario_amount = None
                        sec_scenario_amount = None

                if is_scenario_query:
                    target_amount = None
                    missing = []

                current_amt = float(payload["current_amount"]) if payload.get("current_amount") else (_parse_amount(message) if is_balance_update else None)
                if current_amt is None and heuristic_res.current_amount is not None:
                    current_amt = heuristic_res.current_amount

                cand_contrib = float(payload["monthly_contribution"]) if payload.get("monthly_contribution") else heuristic_res.monthly_contribution

                is_prog = bool(payload.get("is_progress_inquiry")) or heuristic_res.is_progress_inquiry

                needs_clarification = (
                    bool(missing)
                    and not is_scenario_query
                    and not is_prog
                    and not is_balance_update
                    and cand_contrib is None
                )

                return GoalExtractionResult(
                    goal_type=final_type,
                    name=final_name,
                    target_amount=target_amount,
                    timeline_months=timeline_months,
                    target_date=target_date,
                    current_amount=current_amt,
                    monthly_contribution=cand_contrib,
                    is_scenario_query=is_scenario_query,
                    proposed_scenario_amount=proposed_scenario_amount,
                    secondary_scenario_amount=sec_scenario_amount,
                    is_progress_inquiry=is_prog,
                    is_balance_update=is_balance_update,
                    needs_clarification=needs_clarification,
                    missing_fields=missing if needs_clarification else [],
                )
        except Exception as exc:
            logger.warning("LLM goal extraction failed, using heuristic: %s", exc)

        return self.extract_heuristic(message)
