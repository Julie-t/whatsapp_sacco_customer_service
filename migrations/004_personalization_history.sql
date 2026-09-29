-- Migration 004: Member Education History for System 9
-- Tracks educational concepts and financial coaching topics delivered to members.

CREATE TABLE IF NOT EXISTS member_education_history (
    id SERIAL PRIMARY KEY,
    member_id VARCHAR(50) NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    summary TEXT,
    goal_id VARCHAR(100) REFERENCES financial_goals(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_member_education_history_member_id ON member_education_history(member_id);
CREATE INDEX IF NOT EXISTS idx_member_education_history_created_at ON member_education_history(created_at);
