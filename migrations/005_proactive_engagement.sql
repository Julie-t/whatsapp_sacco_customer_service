-- Migration 005: Proactive Engagement, Preferences, Financial News & Continuous Intelligence
-- Apply with: python scripts/migrate.py
-- Depends on: 001_persistence.sql, 002_member_identity.sql, 003_financial_goals.sql, 004_personalization_history.sql

-- 1. Member Engagement Preferences
CREATE TABLE IF NOT EXISTS member_engagement_preferences (
    member_id TEXT PRIMARY KEY REFERENCES members(id) ON DELETE CASCADE,
    education_frequency TEXT NOT NULL DEFAULT 'weekly' CHECK (education_frequency IN ('daily', 'weekly', 'biweekly', 'monthly', 'paused')),
    news_frequency TEXT NOT NULL DEFAULT 'weekly' CHECK (news_frequency IN ('daily', 'weekly', 'monthly', 'paused')),
    goal_alerts_enabled BOOLEAN NOT NULL DEFAULT true,
    allowed_topics TEXT[] NOT NULL DEFAULT ARRAY['budgeting', 'saving', 'compound_interest', 'debt_management', 'emergency_fund'],
    quiet_hours_start INT NOT NULL DEFAULT 20 CHECK (quiet_hours_start >= 0 AND quiet_hours_start <= 23),
    quiet_hours_end INT NOT NULL DEFAULT 8 CHECK (quiet_hours_end >= 0 AND quiet_hours_end <= 23),
    preferred_language TEXT NOT NULL DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Trusted Financial News Articles (SACCO Curated & Approved)
CREATE TABLE IF NOT EXISTS financial_news_articles (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    category TEXT NOT NULL CHECK (category IN ('retirement', 'interest_rates', 'saving_tips', 'inflation', 'sacco_regulations', 'education_funds', 'general_economy')),
    url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiry_at TIMESTAMPTZ NOT NULL,
    is_approved BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_financial_news_category ON financial_news_articles(category);
CREATE INDEX IF NOT EXISTS idx_financial_news_expiry ON financial_news_articles(expiry_at);
CREATE INDEX IF NOT EXISTS idx_financial_news_published_at ON financial_news_articles(published_at DESC);

-- 3. Proactive Notifications & Delivery Tracking
CREATE TABLE IF NOT EXISTS proactive_notifications (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('scheduled_education', 'goal_progress', 'goal_risk', 'financial_news')),
    content_id TEXT,
    message_body TEXT NOT NULL,
    delivery_channel TEXT NOT NULL DEFAULT 'whatsapp',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'failed', 'skipped_quiet_hours', 'skipped_duplicate', 'skipped_paused')),
    sent_at TIMESTAMPTZ,
    feedback TEXT CHECK (feedback IN ('helpful', 'not_helpful')),
    feedback_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proactive_notifications_member_id ON proactive_notifications(member_id);
CREATE INDEX IF NOT EXISTS idx_proactive_notifications_type ON proactive_notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_proactive_notifications_status ON proactive_notifications(status);
CREATE INDEX IF NOT EXISTS idx_proactive_notifications_created_at ON proactive_notifications(created_at DESC);
