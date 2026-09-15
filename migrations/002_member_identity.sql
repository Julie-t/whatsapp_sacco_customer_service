-- Member identity, financial accounts, and loan records.
-- Apply with: python scripts/migrate.py
-- Depends on: 001_persistence.sql

-- Members table
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    phone_hash TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'en',
    knowledge_level TEXT NOT NULL DEFAULT 'beginner',
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    is_demo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Member financial accounts (demo data)
CREATE TABLE IF NOT EXISTS member_accounts (
    id BIGSERIAL PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    account_type TEXT NOT NULL CHECK (account_type IN ('savings', 'shares', 'fixed_deposit', 'target_savings')),
    account_name TEXT NOT NULL,
    balance NUMERIC(15,2) NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'KES',
    is_demo BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Member loans (demo data)
CREATE TABLE IF NOT EXISTS member_loans (
    id BIGSERIAL PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    loan_type TEXT NOT NULL CHECK (loan_type IN ('development', 'emergency', 'school_fees', 'asset_finance')),
    principal NUMERIC(15,2) NOT NULL,
    balance_remaining NUMERIC(15,2) NOT NULL,
    monthly_instalment NUMERIC(15,2) NOT NULL,
    interest_rate NUMERIC(5,2) NOT NULL,
    term_months INTEGER NOT NULL,
    months_paid INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cleared', 'defaulted')),
    currency TEXT NOT NULL DEFAULT 'KES',
    is_demo BOOLEAN NOT NULL DEFAULT true,
    disbursed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Link conversations to resolved members
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS member_id TEXT REFERENCES members(id);

-- Indexes
CREATE INDEX IF NOT EXISTS members_phone_hash ON members(phone_hash);
CREATE INDEX IF NOT EXISTS member_accounts_member ON member_accounts(member_id);
CREATE INDEX IF NOT EXISTS member_loans_member ON member_loans(member_id);
CREATE INDEX IF NOT EXISTS conversations_member ON conversations(member_id);
