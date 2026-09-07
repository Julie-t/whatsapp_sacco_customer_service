#!/usr/bin/env python
"""Fix evaluation dataset source IDs to match actual document IDs."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mapping from expected_source (old) to test document_id (new)
SOURCE_ID_MAP = {
    "compound_interest": "test_compound_interest",
    "loan_types": "test_loan_types",
    "loan_documents": "test_loan_documents",
    "dividends": "test_dividends_interest",
    "membership": "test_membership",
    "loan_repayment": "test_loan_repayment",
    "withdrawal_process": "test_withdrawal_process",
    "savings_interest": "test_savings_interest_rates",
    "budget": "test_budgeting_basics",
    "emergency_fund": "test_emergency_fund",
    "loan_eligibility": "test_loan_eligibility",
    "loan_rates": "test_loan_rates_terms",
    "membership_categories": "test_membership_categories",
    "good_bad_debt": "test_good_bad_debt",
    "membership_eligibility": "test_membership_eligibility",
    "savings_types": "test_savings_types",
    "shares_vs_deposits": "test_shares_vs_deposits",
    "complaints": "test_complaints_disputes",
    "escalation": "test_escalation_channels",
    "deposit_channels": "test_deposit_channels",
    "mobile_banking": "test_mobile_ussd_banking",
    "loan_guarantorship": "test_loan_guarantorship",
    "loan_disbursement": "test_loan_disbursement_delay",
    "consistent_saving": "test_consistent_saving",
    "update_details": "test_update_member_details",
    "balance_statement": "test_balance_statement",
    "savings_minimum": "test_savings_minimum_deposits",
    "withdrawal": "test_withdrawal_process",
    "savings_withdrawal": "test_savings_withdrawals",
    "deposit_missing": "test_deposit_missing",
    "transaction_limits": "test_transaction_limits_fees",
    "investment": "test_investment_literacy",
    "chama": "test_chama_table_banking",
}

def fix_dataset():
    """Update expected_source values in evaluation dataset."""
    dataset_path = Path(__file__).parent.parent / "data/evaluation/rag_eval.json"
    
    with open(dataset_path) as f:
        data = json.load(f)
    
    updated = 0
    for case in data.get("cases", []):
        old_source = case.get("expected_source")
        if old_source and old_source not in [v for v in SOURCE_ID_MAP.values()]:
            # Try to find a match
            for key, test_id in SOURCE_ID_MAP.items():
                if key in old_source.lower():
                    case["expected_source"] = test_id
                    print(f"Updated {case['id']}: {old_source} → {test_id}")
                    updated += 1
                    break
    
    with open(dataset_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nTotal updates: {updated}")

if __name__ == "__main__":
    fix_dataset()
