-- System 12: Production Authentication, SACCO Integration & Secure Member Data
-- Apply with: python scripts/migrate.py
-- Depends on: 001_persistence.sql, 002_member_identity.sql, 006_admin_dashboard.sql

-- 1. Member OTP Challenges Table
CREATE TABLE IF NOT EXISTS member_otp_challenges (
    id TEXT PRIMARY KEY,
    phone_number TEXT NOT NULL,
    phone_hash TEXT NOT NULL,
    otp_code_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_member_otp_phone ON member_otp_challenges(phone_hash, expires_at);
CREATE INDEX IF NOT EXISTS idx_member_otp_sacco ON member_otp_challenges(sacco_id);

-- 2. Authenticated Member Sessions Table (15-30m TTL)
CREATE TABLE IF NOT EXISTS member_sessions (
    session_id TEXT PRIMARY KEY,
    member_id TEXT REFERENCES members(id) ON DELETE CASCADE,
    phone_number TEXT NOT NULL,
    phone_hash TEXT NOT NULL,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    authenticated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_member_sessions_phone ON member_sessions(phone_hash, is_active, expires_at);
CREATE INDEX IF NOT EXISTS idx_member_sessions_member ON member_sessions(member_id, sacco_id);

-- 3. Sensitive Data Access Audit Log
CREATE TABLE IF NOT EXISTS member_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    member_id TEXT,
    phone_hash TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT 'financial_data',
    accessed_fields TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    ip_address TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_member_audit_sacco ON member_audit_logs(sacco_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_audit_member ON member_audit_logs(member_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_audit_action ON member_audit_logs(action);

-- 4. Governed Member Account Change Requests (Read/Write Separation)
CREATE TABLE IF NOT EXISTS member_change_requests (
    id TEXT PRIMARY KEY,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL CHECK (change_type IN ('phone_number', 'next_of_kin', 'email', 'withdrawal_notice', 'other')),
    proposed_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT REFERENCES admin_users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_member_change_requests_sacco ON member_change_requests(sacco_id, status);
CREATE INDEX IF NOT EXISTS idx_member_change_requests_member ON member_change_requests(member_id);
