CREATE TABLE IF NOT EXISTS research_measurements (
    id BIGSERIAL PRIMARY KEY,
    incident_key TEXT NOT NULL UNIQUE,
    dataset_kind TEXT NOT NULL CHECK (
        dataset_kind IN ('demo', 'test', 'real')
    ),

    azure_build_id BIGINT,
    failure_observed_at TIMESTAMPTZ NOT NULL,
    failure_detected_at TIMESTAMPTZ,
    repair_verified_at TIMESTAMPTZ,

    predicted_failure BOOLEAN,
    actual_failure BOOLEAN,

    root_cause_correct BOOLEAN,

    ai_fix_proposed BOOLEAN NOT NULL DEFAULT FALSE,
    ai_fix_tested BOOLEAN NOT NULL DEFAULT FALSE,
    ai_fix_success BOOLEAN,

    rollback_attempted BOOLEAN NOT NULL DEFAULT FALSE,
    rollback_success BOOLEAN,

    reviewer_subject TEXT,
    safe_summary TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        failure_detected_at IS NULL
        OR failure_detected_at >= failure_observed_at
    ),
    CHECK (
        repair_verified_at IS NULL
        OR repair_verified_at >= failure_observed_at
    ),
    CHECK (
        NOT ai_fix_tested
        OR ai_fix_proposed
    )
);

CREATE INDEX IF NOT EXISTS idx_research_measurements_dataset_kind
ON research_measurements (dataset_kind);

CREATE INDEX IF NOT EXISTS idx_research_measurements_created_at
ON research_measurements (created_at DESC);