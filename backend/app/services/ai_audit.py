import os
from typing import Any

import psycopg

from app.services.log_sanitizer import redact_sensitive_text


def safe_audit_text(
    value: Any,
    maximum_length: int,
) -> str:
    return redact_sensitive_text(str(value or ""))[:maximum_length].strip()


def write_ai_audit_event(
    *,
    agent_name: str,
    input_source: str,
    decision_summary: str,
    confidence_percent: float | None,
    action: str,
    result: str,
    user_approval: str = "not_required",
    actor_subject: str | None = None,
    decision_id: int | None = None,
    azure_build_id: int | None = None,
) -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing.")

    allowed_approval_values = {
        "not_required",
        "pending",
        "approved",
        "rejected",
    }

    if user_approval not in allowed_approval_values:
        raise ValueError("Invalid user approval value.")

    if confidence_percent is not None:
        confidence_percent = float(confidence_percent)

        if not 0 <= confidence_percent <= 100:
            raise ValueError("confidence_percent must be between 0 and 100.")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_audit_events (
                    agent_name,
                    input_source,
                    decision_summary,
                    confidence_percent,
                    action,
                    result,
                    user_approval,
                    actor_subject,
                    decision_id,
                    azure_build_id
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                );
                """,
                (
                    safe_audit_text(agent_name, 100),
                    safe_audit_text(input_source, 200),
                    safe_audit_text(decision_summary, 2000),
                    confidence_percent,
                    safe_audit_text(action, 150),
                    safe_audit_text(result, 2000),
                    user_approval,
                    safe_audit_text(actor_subject, 255) if actor_subject else None,
                    decision_id,
                    azure_build_id,
                ),
            )

        connection.commit()
