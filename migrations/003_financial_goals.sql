-- Financial goals and goal-aware planning.
-- Apply with: python scripts/migrate.py
-- Depends on: 002_member_identity.sql

CREATE TABLE IF NOT EXISTS financial_goals (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    goal_type TEXT NOT NULL CHECK (goal_type IN (
        'education',
        'emergency_fund',
        'retirement',
        'asset_purchase',
        'general_savings',
        'business',
        'custom'
    )),
    name TEXT NOT NULL,
    target_amount NUMERIC(15,2) NOT NULL CHECK (target_amount > 0),
    current_amount NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (current_amount >= 0),
    target_date DATE NOT NULL,
    contribution_amount NUMERIC(15,2) DEFAULT NULL,
    contribution_frequency TEXT NOT NULL DEFAULT 'monthly' CHECK (contribution_frequency IN ('monthly', 'weekly', 'lump_sum')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'abandoned')),
    notification_frequency TEXT DEFAULT 'monthly' CHECK (notification_frequency IN ('none', 'weekly', 'monthly', 'quarterly')),
    notes TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS financial_goals_member ON financial_goals(member_id);
CREATE INDEX IF NOT EXISTS financial_goals_status ON financial_goals(status);
CREATE INDEX IF NOT EXISTS financial_goals_target_date ON financial_goals(target_date);
