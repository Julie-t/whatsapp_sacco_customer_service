-- Persistent conversation and knowledge-gap storage.
-- Apply with: python scripts/migrate.py

CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE,
    channel_identifier TEXT NOT NULL,
    channel TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS conversation_messages_lookup
    ON conversation_messages (conversation_id, timestamp DESC, id DESC);
CREATE INDEX IF NOT EXISTS conversations_retention
    ON conversations (last_activity_at);

CREATE TABLE IF NOT EXISTS knowledge_gap_events (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    sacco_id TEXT NOT NULL,
    query TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    retrieval_score DOUBLE PRECISION,
    fallback_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS knowledge_gap_sacco_created
    ON knowledge_gap_events (sacco_id, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_gap_reason
    ON knowledge_gap_events (fallback_reason);
