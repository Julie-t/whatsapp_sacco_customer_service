-- System 11: SACCO Admin Intelligence & Operations Dashboard
-- Apply with: python scripts/migrate.py
-- Depends on: 001_persistence.sql, 002_member_identity.sql, 005_proactive_engagement.sql

-- 1. Admin Users Table
CREATE TABLE IF NOT EXISTS admin_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    role TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('admin', 'staff', 'compliance', 'superadmin')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Member Escalations Table
CREATE TABLE IF NOT EXISTS escalations (
    id BIGSERIAL PRIMARY KEY,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    member_id TEXT REFERENCES members(id) ON DELETE SET NULL,
    conversation_key TEXT NOT NULL,
    query TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'complex_query' CHECK (category IN ('dispute', 'complaint', 'fraud', 'complex_query', 'other')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    notes TEXT,
    assigned_to TEXT REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ
);

-- 3. SACCO Policy & Knowledge Documents Management (Draft -> Review -> Approved -> Ingested)
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'archived')),
    created_by TEXT REFERENCES admin_users(id) ON DELETE SET NULL,
    approved_by TEXT REFERENCES admin_users(id) ON DELETE SET NULL,
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    qdrant_indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Admin Audit Logs Table
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    sacco_id TEXT NOT NULL DEFAULT 'demo_sacco',
    admin_id TEXT REFERENCES admin_users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details JSONB,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance and tenant queries
CREATE INDEX IF NOT EXISTS admin_users_sacco ON admin_users(sacco_id);
CREATE INDEX IF NOT EXISTS escalations_sacco_status ON escalations(sacco_id, status);
CREATE INDEX IF NOT EXISTS escalations_created ON escalations(created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_documents_sacco_status ON knowledge_documents(sacco_id, status);
CREATE INDEX IF NOT EXISTS admin_audit_logs_sacco ON admin_audit_logs(sacco_id, created_at DESC);
