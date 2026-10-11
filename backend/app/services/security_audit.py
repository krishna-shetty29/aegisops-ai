import os
from typing import Optional

import psycopg


def _safe_text(value: object, maximum_length: int) -> str:
    return str(value or "").strip()[:maximum_length]


def write_security_audit(
    *,
    actor_subject: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    outcome: str,
    summary: str,
) -> None:
    """
    Writes safe metadata only.

    Never pass request headers, bearer tokens, PATs, database URLs,
    prompts, raw logs, or secret values to this function.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing.")

    if outcome not in {"allowed", "denied", "error"}:
        raise ValueError("Audit outcome is invalid.")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO security_audit_logs (
                    actor_subject,
                    actor_role,
                    action,
                    resource_type,
                    resource_id,
                    outcome,
                    summary
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    _safe_text(actor_subject, 255),
                    _safe_text(actor_role, 255),
                    _safe_text(action, 100),
                    _safe_text(resource_type, 100),
                    _safe_text(resource_id, 255) or None,
                    _safe_text(outcome, 20),
                    _safe_text(summary, 1000),
                ),
            )

        connection.commit()
