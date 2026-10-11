import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

from app.services.decision_status import (
    DecisionStatus,
    validate_status_transition,
)
from app.services.failure_risk_service import predict_failure_risk
from typing import Any, cast

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")


SAFE_FEATURE_COLUMNS = [
    "files_changed",
    "changes_count",
    "previous_failures_10",
    "dependency_changes",
    "previous_deployment_failures_10",
]


class DecisionAlreadyExistsError(RuntimeError):
    """Raised when a decision already exists for an Azure build."""


class DecisionStorageError(RuntimeError):
    """Raised when a decision cannot be saved safely."""


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise DecisionStorageError("DATABASE_URL is missing from the root .env file.")

    return database_url


def _validate_non_negative_features(features: dict) -> dict:
    validated_features = {}

    for column in SAFE_FEATURE_COLUMNS:
        if column not in features:
            raise ValueError(f"Missing safe feature: {column}")

        value = features[column]

        if isinstance(value, bool):
            raise ValueError(f"{column} must be a non-negative integer.")

        try:
            validated_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{column} must be a non-negative integer.") from exc

        if validated_value < 0:
            raise ValueError(f"{column} must be a non-negative integer.")

        validated_features[column] = validated_value

    return validated_features


def _validate_reference(value: str, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise ValueError(f"{field_name} is required.")

    return cleaned_value


def evaluate_failure_risk_decision(
    *,
    azure_build_id: int,
    branch_name: str,
    commit_sha: str,
    features: dict,
) -> dict:
    """
    Creates one review-only decision record for a build.

    This function only:
    - reads the trained local model;
    - writes an audit record to PostgreSQL;
    - returns a human recommendation.

    It does not create branches or PRs, run pipelines, deploy, roll back,
    call Terraform, or call Kubernetes.
    """
    if isinstance(azure_build_id, bool):
        raise ValueError("azure_build_id must be a positive integer.")

    try:
        validated_build_id = int(azure_build_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("azure_build_id must be a positive integer.") from exc

    if validated_build_id <= 0:
        raise ValueError("azure_build_id must be a positive integer.")

    validated_branch_name = _validate_reference(
        branch_name,
        "branch_name",
    )
    validated_commit_sha = _validate_reference(
        commit_sha,
        "commit_sha",
    )
    validated_features = _validate_non_negative_features(features)

    prediction = predict_failure_risk(validated_features)

    probability_percent = float(prediction["failure_probability_percent"])
    is_high_risk = probability_percent >= 70.0

    decision_status = (
        DecisionStatus.HUMAN_REVIEW_RECOMMENDED
        if is_high_risk
        else DecisionStatus.NORMAL_REVIEW
    )

    concise_summary = (
        "This pre-build estimate indicates elevated failure risk."
        if is_high_risk
        else "This pre-build estimate indicates normal failure risk."
    )

    recommended_human_action = (
        "Review changed dependencies, recent build history, and "
        "test coverage before approval."
        if is_high_risk
        else "Continue with the normal human review process."
    )

    insert_query = """
        INSERT INTO autonomous_decisions (
            azure_build_id,
            branch_name,
            commit_sha,
            files_changed,
            changes_count,
            previous_failures_10,
            dependency_changes,
            previous_deployment_failures_10,
            failure_probability_percent,
            risk_level,
            decision_status,
            concise_summary,
            recommended_human_action
        )
        VALUES (
            %(azure_build_id)s,
            %(branch_name)s,
            %(commit_sha)s,
            %(files_changed)s,
            %(changes_count)s,
            %(previous_failures_10)s,
            %(dependency_changes)s,
            %(previous_deployment_failures_10)s,
            %(failure_probability_percent)s,
            %(risk_level)s,
            %(decision_status)s,
            %(concise_summary)s,
            %(recommended_human_action)s
        )
        ON CONFLICT (azure_build_id) DO NOTHING
        RETURNING id;
    """

    insert_values = {
        "azure_build_id": validated_build_id,
        "branch_name": validated_branch_name,
        "commit_sha": validated_commit_sha,
        "files_changed": validated_features["files_changed"],
        "changes_count": validated_features["changes_count"],
        "previous_failures_10": validated_features["previous_failures_10"],
        "dependency_changes": validated_features["dependency_changes"],
        "previous_deployment_failures_10": validated_features[
            "previous_deployment_failures_10"
        ],
        "failure_probability_percent": probability_percent,
        "risk_level": "high" if is_high_risk else "normal",
        "decision_status": decision_status.value,
        "concise_summary": concise_summary,
        "recommended_human_action": recommended_human_action,
    }

    try:
        with psycopg.connect(_get_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(insert_query, insert_values)
                created_row = cursor.fetchone()

            connection.commit()
    except psycopg.Error as exc:
        raise DecisionStorageError(
            "The decision could not be stored in PostgreSQL."
        ) from exc

    if not created_row:
        raise DecisionAlreadyExistsError(
            "A decision already exists for this Azure build ID."
        )

    decision_id = created_row[0]

    return {
        "decision_id": decision_id,
        "decision_status": decision_status.value,
        "failure_probability_percent": probability_percent,
        "risk_level": "high" if is_high_risk else "normal",
        "model_type": prediction.get(
            "model_type",
            "logistic_regression",
        ),
        "summary": concise_summary,
        "recommended_human_action": recommended_human_action,
    }


def _format_decision_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision_id": row["id"],
        "azure_build_id": row["azure_build_id"],
        "branch_name": row["branch_name"],
        "commit_sha": row["commit_sha"],
        "features_used": {
            "files_changed": row["files_changed"],
            "changes_count": row["changes_count"],
            "previous_failures_10": row["previous_failures_10"],
            "dependency_changes": row["dependency_changes"],
            "previous_deployment_failures_10": (row["previous_deployment_failures_10"]),
        },
        "failure_probability_percent": (
            float(row["failure_probability_percent"])
            if row["failure_probability_percent"] is not None
            else None
        ),
        "risk_level": row["risk_level"],
        "decision_status": row["decision_status"],
        "summary": row["concise_summary"],
        "recommended_human_action": (row["recommended_human_action"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_decisions(limit: int = 25) -> list[dict]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")

    query = """
        SELECT
            id,
            azure_build_id,
            branch_name,
            commit_sha,
            files_changed,
            changes_count,
            previous_failures_10,
            dependency_changes,
            previous_deployment_failures_10,
            failure_probability_percent,
            risk_level,
            decision_status,
            concise_summary,
            recommended_human_action,
            created_at,
            updated_at
        FROM autonomous_decisions
        ORDER BY created_at DESC
        LIMIT %s;
    """

    try:
        with psycopg.connect(
            _get_database_url(),
            row_factory=cast(Any, dict_row),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (limit,))
                rows = cast(
                    list[dict[str, Any]],
                    cursor.fetchall(),
                )
    except psycopg.Error as exc:
        raise DecisionStorageError(
            "Decision records could not be read from PostgreSQL."
        ) from exc

    return [_format_decision_row(row) for row in rows]


def get_decision_by_id(decision_id: int) -> dict | None:
    if decision_id <= 0:
        raise ValueError("decision_id must be a positive integer.")

    query = """
        SELECT
            id,
            azure_build_id,
            branch_name,
            commit_sha,
            files_changed,
            changes_count,
            previous_failures_10,
            dependency_changes,
            previous_deployment_failures_10,
            failure_probability_percent,
            risk_level,
            decision_status,
            concise_summary,
            recommended_human_action,
            created_at,
            updated_at
        FROM autonomous_decisions
        WHERE id = %s;
    """

    try:
        with psycopg.connect(
            _get_database_url(),
            row_factory=cast(Any, dict_row),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (decision_id,))
                row = cast(
                    dict[str, Any] | None,
                    cursor.fetchone(),
                )
    except psycopg.Error as exc:
        raise DecisionStorageError(
            "The decision record could not be read from PostgreSQL."
        ) from exc

    if row is None:
        return None

    return _format_decision_row(row)


def approve_fix_for_pr_review(
    decision_id: int,
) -> dict | None:
    """
    Makes only the local transition:

    fix_proposed -> awaiting_pr_approval

    It does not create an Azure DevOps pull request.
    """
    if decision_id <= 0:
        raise ValueError("decision_id must be a positive integer.")

    target_status = DecisionStatus.AWAITING_PR_APPROVAL

    try:
        with psycopg.connect(
            _get_database_url(),
            row_factory=cast(Any, dict_row),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, decision_status
                    FROM autonomous_decisions
                    WHERE id = %s
                    FOR UPDATE;
                    """,
                    (decision_id,),
                )
                row = cast(
                    dict[str, Any] | None,
                    cursor.fetchone(),
                )

                if row is None:
                    return None

                current_status = DecisionStatus(str(row["decision_status"]))

                validate_status_transition(
                    current_status,
                    target_status,
                )

                cursor.execute(
                    """
                    UPDATE autonomous_decisions
                    SET decision_status = %s,
                        updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (
                        target_status.value,
                        decision_id,
                    ),
                )

            connection.commit()

    except psycopg.Error as exc:
        raise DecisionStorageError("The decision status could not be updated.") from exc

    return {
        "decision_id": decision_id,
        "previous_status": current_status.value,
        "decision_status": target_status.value,
        "automatic_action_taken": False,
    }
