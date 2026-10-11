import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise SystemExit("DATABASE_URL is missing.")


sql = """
CREATE TABLE IF NOT EXISTS ai_audit_events (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    agent_name TEXT NOT NULL,
    input_source TEXT NOT NULL,
    decision_summary TEXT NOT NULL,

    confidence_percent NUMERIC(5,2),
    action TEXT NOT NULL,
    result TEXT NOT NULL,

    user_approval TEXT NOT NULL DEFAULT 'not_required',
    actor_subject TEXT,

    decision_id BIGINT,
    azure_build_id BIGINT,

    CONSTRAINT ai_audit_confidence_range
        CHECK (
            confidence_percent IS NULL
            OR (
                confidence_percent >= 0
                AND confidence_percent <= 100
            )
        ),

    CONSTRAINT ai_audit_approval_value
        CHECK (
            user_approval IN (
                'not_required',
                'pending',
                'approved',
                'rejected'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_ai_audit_events_occurred_at
ON ai_audit_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_audit_events_decision_id
ON ai_audit_events (decision_id);
"""


with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()

print("ai_audit_events table is ready.")
