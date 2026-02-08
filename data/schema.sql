-- CupidsShield Database Schema
-- Trust & Safety moderation and appeals tracking

-- Moderation cases table
CREATE TABLE IF NOT EXISTS moderation_cases (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL CHECK(content_type IN ('profile', 'message', 'photo', 'bio')),
    content TEXT NOT NULL,
    user_id TEXT NOT NULL,
    risk_score REAL CHECK(risk_score >= 0 AND risk_score <= 1),
    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected', 'escalated', 'pending')),
    reasoning TEXT NOT NULL,
    confidence REAL CHECK(confidence >= 0 AND confidence <= 1),
    violation_type TEXT,  -- 'harassment', 'scam', 'fake_profile', 'inappropriate', 'age_verification'
    severity TEXT CHECK(severity IN ('low', 'medium', 'high', 'critical')),
    reviewed_by TEXT NOT NULL,  -- 'agent' or moderator_id
    metadata TEXT,  -- JSON string with additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Appeals table
CREATE TABLE IF NOT EXISTS appeals (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES moderation_cases(id) ON DELETE CASCADE,
    user_explanation TEXT NOT NULL,
    new_evidence TEXT,  -- Additional evidence provided by user
    appeal_decision TEXT CHECK(appeal_decision IN ('upheld', 'overturned', 'escalated', 'pending')),
    appeal_reasoning TEXT,
    appeal_confidence REAL CHECK(appeal_confidence >= 0 AND appeal_confidence <= 1),
    resolved_by TEXT,  -- 'agent' or moderator_id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Audit log for all actions
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    appeal_id TEXT,
    action TEXT NOT NULL,  -- 'case_created', 'decision_made', 'appeal_filed', 'escalated', etc.
    actor TEXT NOT NULL,  -- 'agent', moderator_id, or 'system'
    details TEXT,  -- JSON string with action details
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES moderation_cases(id) ON DELETE SET NULL,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id) ON DELETE SET NULL
);

-- User violation history (for pattern detection)
CREATE TABLE IF NOT EXISTS user_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    case_id TEXT NOT NULL REFERENCES moderation_cases(id) ON DELETE CASCADE,
    violation_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Moderator review queue
CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    case_id TEXT REFERENCES moderation_cases(id) ON DELETE CASCADE,
    appeal_id TEXT REFERENCES appeals(id) ON DELETE CASCADE,
    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    assigned_to TEXT,  -- moderator_id or NULL if unassigned
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'in_review', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    CHECK ((case_id IS NOT NULL AND appeal_id IS NULL) OR (case_id IS NULL AND appeal_id IS NOT NULL))
);

-- Metrics and statistics
CREATE TABLE IF NOT EXISTS metrics_snapshot (
    id TEXT PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_metadata TEXT,  -- JSON string with additional context
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cases_user_id ON moderation_cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_decision ON moderation_cases(decision);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON moderation_cases(created_at);
CREATE INDEX IF NOT EXISTS idx_cases_violation_type ON moderation_cases(violation_type);
CREATE INDEX IF NOT EXISTS idx_appeals_case_id ON appeals(case_id);
CREATE INDEX IF NOT EXISTS idx_appeals_decision ON appeals(appeal_decision);
CREATE INDEX IF NOT EXISTS idx_audit_case_id ON audit_log(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_violations_user_id ON user_violations(user_id);
CREATE INDEX IF NOT EXISTS idx_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON review_queue(priority);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics_snapshot(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics_snapshot(timestamp);

-- Trigger to update updated_at on moderation_cases
CREATE TRIGGER IF NOT EXISTS update_cases_timestamp
AFTER UPDATE ON moderation_cases
BEGIN
    UPDATE moderation_cases SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
