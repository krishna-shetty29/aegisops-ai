import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Literal, cast, overload

import httpx
import psycopg
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field

from app.agents.pipeline_graph import PipelineState, pipeline_graph
from app.core.automation_safety import ensure_automation_is_disabled
from app.core.security import Principal, require_roles
from app.services.ai_log_analyzer import (
    FailureAnalysis,
    analyze_pipeline_failure,
)
from app.services.decision_engine import (
    DecisionAlreadyExistsError,
    DecisionStorageError,
    approve_fix_for_pr_review,
    evaluate_failure_risk_decision,
    get_decision_by_id,
    list_decisions,
)
from app.services.failure_risk_service import (
    FailureRiskModelUnavailable,
    predict_failure_risk,
)
from app.services.infrastructure_assessment import (
    build_infrastructure_assessment,
)
from app.services.log_parser import parse_log
from app.services.log_sanitizer import redact_sensitive_text
from app.services.prometheus_service import get_infrastructure_summary
from app.services.rag_service import (
    format_knowledge_context,
    index_knowledge_base_folder,
    search_knowledge,
)
from app.services.root_cause_evidence import inspect_infrastructure_state
from app.services.security_audit import write_security_audit
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.services.ai_audit import write_ai_audit_event


class FailureRiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files_changed: int = Field(ge=0, le=100000)
    changes_count: int = Field(ge=0, le=100000)
    previous_failures_10: int = Field(ge=0, le=10)
    dependency_changes: int = Field(ge=0, le=100000)
    previous_deployment_failures_10: int = Field(ge=0, le=10)


class DecisionEngineRequest(FailureRiskRequest):
    model_config = ConfigDict(extra="forbid")

    azure_build_id: int = Field(gt=0)
    branch_name: str = Field(min_length=1, max_length=255)
    commit_sha: str = Field(min_length=1, max_length=100)


class CreateFixBranchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: int = Field(gt=0)
    file_path: str = Field(min_length=1, max_length=500)
    replacement_content: str = Field(min_length=1)
    human_approved: bool = False
    target_environment: Literal[
        "development",
        "test",
        "staging",
    ] = "development"


class CreatePullRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: int = Field(gt=0)
    root_cause: str = Field(min_length=1)
    proposed_fix: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    human_approved: bool = False


class TestResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    azure_build_id: int = Field(gt=0)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

app = FastAPI(
    title="Autonomous AI DevOps Engineer API",
    version="1.0.0",
)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


def rate_limit_handler(
    request: Request,
    exc: Exception,
) -> Response:
    if not isinstance(exc, RateLimitExceeded):
        raise exc

    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_handler,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


def safe_text(value: Any, maximum_length: int = 2000) -> str:
    if value is None:
        return ""

    return redact_sensitive_text(str(value))[:maximum_length]


def safe_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return safe_text(value)

    if isinstance(value, list):
        return [safe_json_value(item) for item in value[:50]]

    if isinstance(value, dict):
        return {
            safe_text(key, 150): safe_json_value(item) for key, item in value.items()
        }

    return value


def principal_role(principal: Principal) -> str:
    return ",".join(sorted(principal.roles)) or "none"


def write_audit(
    principal: Principal,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    summary: str,
) -> None:
    write_security_audit(
        actor_subject=principal.subject,
        actor_role=principal_role(principal),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        summary=summary,
    )


def feature_payload(request: FailureRiskRequest) -> dict[str, int]:
    return {
        "files_changed": request.files_changed,
        "changes_count": request.changes_count,
        "previous_failures_10": request.previous_failures_10,
        "dependency_changes": request.dependency_changes,
        "previous_deployment_failures_10": (request.previous_deployment_failures_10),
    }


def failure_analysis_to_safe_response(
    analysis: FailureAnalysis,
) -> dict[str, Any]:
    return {
        "failure_type": safe_text(analysis.failure_type, 300),
        "root_cause": safe_text(analysis.root_cause, 2000),
        "evidence": [safe_text(item, 1000) for item in analysis.evidence[:20]],
        "severity": safe_text(analysis.severity, 100),
        "confidence": analysis.confidence,
        "suggested_fix": safe_text(analysis.suggested_fix, 2000),
        "affected_files": [
            safe_text(item, 300) for item in analysis.affected_files[:50]
        ],
    }


def safe_fix_proposal(proposal: Any) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        return {}

    tests_required = proposal.get("tests_required", [])

    if not isinstance(tests_required, list):
        tests_required = []

    return {
        "modified_file": safe_text(
            proposal.get("modified_file", ""),
            300,
        ),
        "explanation": safe_text(
            proposal.get("explanation", ""),
            2000,
        ),
        "tests_required": [safe_text(item, 500) for item in tests_required[:20]],
        "confidence": proposal.get("confidence"),
        "requires_human_approval": True,
    }


AZURE_ORG = os.getenv("AZURE_DEVOPS_ORG") or os.getenv("AZURE_DEVOPS_ORGANIZATION")
AZURE_PROJECT = os.getenv("AZURE_DEVOPS_PROJECT")
AZURE_PAT = os.getenv("AZURE_DEVOPS_PAT")
AZURE_API_VERSION = "7.1"

if AZURE_ORG and not os.getenv("AZURE_DEVOPS_ORGANIZATION"):
    os.environ["AZURE_DEVOPS_ORGANIZATION"] = AZURE_ORG

AZURE_BASE_URL = (
    f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}"
    if AZURE_ORG and AZURE_PROJECT
    else None
)


@overload
def azure_get(path: str, as_text: Literal[True]) -> str: ...


@overload
def azure_get(
    path: str,
    as_text: Literal[False] = False,
) -> dict[str, Any]: ...


def azure_get(
    path: str,
    as_text: bool = False,
) -> dict[str, Any] | str:
    if not AZURE_BASE_URL or not AZURE_PAT:
        raise HTTPException(
            status_code=500,
            detail=(
                "Azure DevOps configuration is missing. "
                "Check AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, "
                "and AZURE_DEVOPS_PAT in the root .env file."
            ),
        )

    separator = "&" if "?" in path else "?"
    url = f"{AZURE_BASE_URL}{path}" f"{separator}api-version={AZURE_API_VERSION}"

    response = requests.get(
        url,
        auth=("", AZURE_PAT),
        timeout=30,
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail="Azure DevOps request failed.",
        )

    if as_text:
        return response.text

    payload = response.json()

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="Azure DevOps returned an unexpected response.",
        )

    return payload


@app.get("/")
def root():
    return {
        "message": "Autonomous AI DevOps Engineer API is running.",
        "safety": (
            "All predictions and analyses are review-only. "
            "No automatic branch creation, pull-request creation, "
            "deployment, rollback, Kubernetes, or Terraform action occurs."
        ),
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/api/predictions/failure-risk")
def get_failure_risk_prediction(
    request: FailureRiskRequest,
    principal: Principal = Depends(require_roles("reviewer", "admin", "agent")),
):
    try:
        return predict_failure_risk(feature_payload(request))

    except FailureRiskModelUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@app.post("/api/decision-engine/evaluate")
@limiter.limit("10/minute")
def evaluate_decision_engine(
    request: Request,
    payload: DecisionEngineRequest,
    principal: Principal = Depends(require_roles("reviewer", "admin", "agent")),
):
    try:
        result = evaluate_failure_risk_decision(
            azure_build_id=payload.azure_build_id,
            branch_name=payload.branch_name,
            commit_sha=payload.commit_sha,
            features=feature_payload(payload),
        )

        write_audit(
            principal=principal,
            action="decision_evaluated",
            resource_type="azure_build",
            resource_id=str(payload.azure_build_id),
            outcome="allowed",
            summary="Safe pre-build failure-risk estimate was recorded.",
        )
        write_ai_audit_event(
            agent_name="Failure Risk Agent",
            input_source="Safe build feature counts",
            decision_summary=("Failure-risk prediction was recorded for human review."),
            confidence_percent=None,
            action="risk_prediction_recorded",
            result="Local decision record created.",
            user_approval="not_required",
            actor_subject=principal.subject,
            decision_id=result["decision_id"],
            azure_build_id=payload.azure_build_id,
        )

        return result

    except DecisionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="A decision already exists for this Azure build ID.",
        ) from exc

    except DecisionStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="The decision could not be stored locally.",
        ) from exc

    except FailureRiskModelUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="The security audit record could not be stored.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.get("/api/decision-engine/decisions")
@limiter.limit("60/minute")
def get_decision_records(
    request: Request,
    limit: int = 50,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    try:
        return {"decisions": list_decisions(limit=limit)}

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except DecisionStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Decision records are currently unavailable.",
        ) from exc


@app.get("/api/decision-engine/decisions/{decision_id}")
def get_decision_record(
    decision_id: int,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    try:
        decision = get_decision_by_id(decision_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except DecisionStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Decision records are currently unavailable.",
        ) from exc

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail="Decision record not found.",
        )

    return decision


@app.post("/api/decision-engine/decisions/{decision_id}/record-test-result")
def record_test_result(
    decision_id: int,
    request: TestResultRequest,
    principal: Principal = Depends(require_roles("reviewer", "admin")),
):
    build = azure_get(f"/_apis/build/builds/{request.azure_build_id}")

    build_status = str(build.get("status", "")).lower()
    build_result = str(build.get("result", "")).lower()
    source_branch = str(build.get("sourceBranch", ""))

    if build_status != "completed":
        raise HTTPException(
            status_code=409,
            detail="The Azure Pipeline has not completed yet.",
        )

    if not source_branch.startswith("refs/pull/"):
        raise HTTPException(
            status_code=409,
            detail=(
                "This endpoint accepts only a completed " "pull-request pipeline build."
            ),
        )

    if build_result == "succeeded":
        test_status = "tests_passed"
        summary = "Tests passed — human deployment approval required."
    elif build_result == "failed":
        test_status = "tests_failed"
        summary = "Tests failed — review the failure evidence " "and revise manually."
    else:
        raise HTTPException(
            status_code=409,
            detail=(
                "The completed pipeline has no supported pass/fail " "test result."
            ),
        )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is missing.",
        )

    try:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT decision_status
                    FROM autonomous_decisions
                    WHERE id = %s;
                    """,
                    (decision_id,),
                )
                decision_row = cursor.fetchone()

                if decision_row is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Decision record not found.",
                    )

                if str(decision_row[0]) != "awaiting_pr_approval":
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "The decision must be awaiting PR approval "
                            "before recording test results."
                        ),
                    )

                cursor.execute(
                    """
                    INSERT INTO decision_test_results (
                        decision_id,
                        azure_build_id,
                        test_status,
                        summary
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (azure_build_id) DO NOTHING
                    RETURNING id;
                    """,
                    (
                        decision_id,
                        request.azure_build_id,
                        test_status,
                        summary,
                    ),
                )

                test_result_row = cursor.fetchone()

                if test_result_row is None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "A test result has already been recorded "
                            "for this Azure build ID."
                        ),
                    )

                cursor.execute(
                    """
                    UPDATE autonomous_decisions
                    SET decision_status = %s,
                        updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (test_status, decision_id),
                )

            connection.commit()

        write_audit(
            principal=principal,
            action="test_result_recorded",
            resource_type="azure_build",
            resource_id=str(request.azure_build_id),
            outcome="allowed",
            summary=(
                "Completed pull-request pipeline test result " "was recorded locally."
            ),
        )

    except HTTPException:
        raise

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="The local test result could not be recorded.",
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="The security audit record could not be stored.",
        ) from exc

    return {
        "decision_id": decision_id,
        "azure_build_id": request.azure_build_id,
        "decision_status": test_status,
        "summary": summary,
        "automatic_action_taken": False,
    }


@app.get("/api/projects")
def get_projects(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    if not AZURE_ORG or not AZURE_PAT:
        raise HTTPException(
            status_code=500,
            detail="Azure DevOps configuration is missing.",
        )

    response = requests.get(
        f"https://dev.azure.com/{AZURE_ORG}/_apis/projects"
        f"?api-version={AZURE_API_VERSION}",
        auth=("", AZURE_PAT),
        timeout=30,
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail="Azure DevOps request failed.",
        )

    return response.json()


@app.get("/api/repositories")
def get_repositories(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    return azure_get("/_apis/git/repositories")


@app.get("/api/pipelines")
def get_pipelines(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    return azure_get("/_apis/pipelines")


@app.get("/api/builds")
def get_builds(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    return azure_get("/_apis/build/builds?$top=50")


@app.get("/api/builds/{build_id}")
def get_build(
    build_id: int,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    return azure_get(f"/_apis/build/builds/{build_id}")


def get_failed_build_or_raise(build_id: int) -> dict[str, Any]:
    build = azure_get(f"/_apis/build/builds/{build_id}")

    result = str(build.get("result", "")).lower()
    status = str(build.get("status", "")).lower()

    if status != "completed" or result != "failed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Failure analysis is available only after a build "
                "has completed with result 'failed'."
            ),
        )

    return build


def extract_log_details(
    log_text: str,
) -> tuple[list[str], list[str], list[str]]:
    log_text = redact_sensitive_text(log_text)

    error_lines: list[str] = []
    warning_lines: list[str] = []
    exit_codes: list[str] = []

    for line in log_text.splitlines():
        lower_line = line.lower()

        if "error" in lower_line or "failed" in lower_line:
            error_lines.append(line[:1000])

        if "warning" in lower_line:
            warning_lines.append(line[:1000])

        exit_codes.extend(
            re.findall(
                r"(?:exit code|code)\s*['\"]?(\d+)['\"]?",
                lower_line,
            )
        )

    return (
        error_lines[:100],
        warning_lines[:100],
        exit_codes[:50],
    )


def save_log_to_database(
    build_id: int,
    log_id: int,
    log_text: str,
    error_lines: list[str],
    warning_lines: list[str],
    exit_codes: list[str],
) -> None:
    log_text = redact_sensitive_text(log_text)
    error_lines = [redact_sensitive_text(line) for line in error_lines]
    warning_lines = [redact_sensitive_text(line) for line in warning_lines]

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is missing.",
        )

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO build_logs (
                    build_id,
                    log_id,
                    log_text,
                    error_lines,
                    warning_lines,
                    exit_codes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (build_id, log_id)
                DO UPDATE SET
                    log_text = EXCLUDED.log_text,
                    error_lines = EXCLUDED.error_lines,
                    warning_lines = EXCLUDED.warning_lines,
                    exit_codes = EXCLUDED.exit_codes,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    build_id,
                    log_id,
                    log_text,
                    json.dumps(error_lines),
                    json.dumps(warning_lines),
                    json.dumps(exit_codes),
                ),
            )


def collect_and_store_logs(build_id: int) -> dict[str, Any]:
    get_failed_build_or_raise(build_id)

    timeline = azure_get(f"/_apis/build/builds/{build_id}/timeline")
    records = timeline.get("records", [])

    log_records = [
        record for record in records if record.get("log") and record["log"].get("id")
    ]

    stored_count = 0

    for record in log_records:
        log_id = record["log"]["id"]

        log_text = azure_get(
            f"/_apis/build/builds/{build_id}/logs/{log_id}",
            as_text=True,
        )

        log_text = redact_sensitive_text(log_text)

        (
            error_lines,
            warning_lines,
            exit_codes,
        ) = extract_log_details(log_text)

        save_log_to_database(
            build_id=build_id,
            log_id=log_id,
            log_text=log_text,
            error_lines=error_lines,
            warning_lines=warning_lines,
            exit_codes=exit_codes,
        )

        stored_count += 1

    return {
        "build_id": build_id,
        "stored_log_count": stored_count,
        "message": "Redacted failed-build logs were stored locally.",
    }


def read_build_logs_as_text(build_id: int) -> str:
    timeline = azure_get(f"/_apis/build/builds/{build_id}/timeline")
    records = timeline.get("records", [])

    log_records = [
        record for record in records if record.get("log") and record["log"].get("id")
    ]

    all_logs: list[str] = []

    for record in log_records:
        log_id = record["log"]["id"]

        log_text = azure_get(
            f"/_apis/build/builds/{build_id}/logs/{log_id}",
            as_text=True,
        )

        all_logs.append(redact_sensitive_text(log_text))

    return "\n".join(all_logs)


@app.get("/api/builds/{build_id}/logs")
def get_build_logs(
    build_id: int,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    get_failed_build_or_raise(build_id)

    logs = azure_get(f"/_apis/build/builds/{build_id}/logs")

    safe_logs = [
        {
            "id": log.get("id"),
            "type": log.get("type"),
            "created_on": log.get("createdOn"),
            "last_changed_on": log.get("lastChangedOn"),
        }
        for log in logs.get("value", [])
    ]

    return {
        "build_id": build_id,
        "logs": safe_logs,
    }


@app.post("/api/builds/{build_id}/collect-logs")
def collect_logs(
    build_id: int,
    principal: Principal = Depends(require_roles("reviewer", "admin", "agent")),
):
    result = collect_and_store_logs(build_id)

    write_audit(
        principal=principal,
        action="failed_build_logs_collected",
        resource_type="azure_build",
        resource_id=str(build_id),
        outcome="allowed",
        summary="Redacted failed-build logs were collected locally.",
    )

    return result


def save_failure_analysis(
    build_id: int,
    analysis: FailureAnalysis,
) -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is missing.",
        )

    safe_analysis = failure_analysis_to_safe_response(analysis)

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO failure_analyses (
                    build_id,
                    failure_type,
                    root_cause,
                    evidence,
                    severity,
                    confidence,
                    suggested_fix,
                    affected_files
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (build_id)
                DO UPDATE SET
                    failure_type = EXCLUDED.failure_type,
                    root_cause = EXCLUDED.root_cause,
                    evidence = EXCLUDED.evidence,
                    severity = EXCLUDED.severity,
                    confidence = EXCLUDED.confidence,
                    suggested_fix = EXCLUDED.suggested_fix,
                    affected_files = EXCLUDED.affected_files,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    build_id,
                    safe_analysis["failure_type"],
                    safe_analysis["root_cause"],
                    json.dumps(safe_analysis["evidence"]),
                    safe_analysis["severity"],
                    safe_analysis["confidence"],
                    safe_analysis["suggested_fix"],
                    json.dumps(safe_analysis["affected_files"]),
                ),
            )


def load_failure_analysis(build_id: int) -> dict[str, Any] | None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is missing.",
        )

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    build_id,
                    failure_type,
                    root_cause,
                    evidence,
                    severity,
                    confidence,
                    suggested_fix,
                    affected_files,
                    created_at
                FROM failure_analyses
                WHERE build_id = %s
                """,
                (build_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    evidence = row[3]
    affected_files = row[7]

    if isinstance(evidence, str):
        evidence = json.loads(evidence)

    if isinstance(affected_files, str):
        affected_files = json.loads(affected_files)

    return {
        "build_id": row[0],
        "failure_type": safe_text(row[1], 300),
        "root_cause": safe_text(row[2], 2000),
        "evidence": [safe_text(item, 1000) for item in (evidence or [])],
        "severity": safe_text(row[4], 100),
        "confidence": row[5],
        "suggested_fix": safe_text(row[6], 2000),
        "affected_files": [safe_text(item, 300) for item in (affected_files or [])],
        "created_at": row[8],
    }


@app.post("/api/analyze/{build_id}")
def analyze_build(
    build_id: int,
    principal: Principal = Depends(require_roles("reviewer", "admin", "agent")),
):
    build = get_failed_build_or_raise(build_id)

    raw_logs = read_build_logs_as_text(build_id)
    parsed_log = parse_log(raw_logs)

    knowledge_results = search_knowledge(parsed_log["relevant_context"][:4000])

    analysis = analyze_pipeline_failure(
        pipeline_name=build.get(
            "definition",
            {},
        ).get("name", "Unknown"),
        build_id=build_id,
        commit=build.get("sourceVersion", "Unknown"),
        relevant_logs=parsed_log["relevant_context"],
        changed_files=[],
        environment="local_review",
        knowledge_context=format_knowledge_context(knowledge_results),
        pipeline_configuration={},
        infrastructure_state=inspect_infrastructure_state(),
    )

    save_failure_analysis(build_id, analysis)

    write_audit(
        principal=principal,
        action="failed_build_analyzed",
        resource_type="azure_build",
        resource_id=str(build_id),
        outcome="allowed",
        summary="Safe failed-build evidence analysis was requested.",
    )
    write_ai_audit_event(
        agent_name="Root Cause Agent",
        input_source="Redacted Azure Pipeline log evidence",
        decision_summary=("A concise failed-build root-cause analysis was prepared."),
        confidence_percent=analysis.confidence * 100,
        action="failure_analysis_completed",
        result="Evidence saved locally for human review.",
        user_approval="pending",
        actor_subject=principal.subject,
        azure_build_id=build_id,
    )

    return {
        "build_id": build_id,
        "analysis": failure_analysis_to_safe_response(analysis),
        "message": "Reviewable failure analysis is ready.",
    }


@app.get("/api/failure-analyses/{build_id}")
def get_failure_analysis(
    build_id: int,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    analysis = load_failure_analysis(build_id)

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="No saved failure analysis exists for this build.",
        )

    return analysis


@app.post("/api/knowledge/index")
def index_knowledge(
    principal: Principal = Depends(require_roles("admin")),
):
    result = index_knowledge_base_folder()

    write_audit(
        principal=principal,
        action="knowledge_indexed",
        resource_type="knowledge_base",
        resource_id=None,
        outcome="allowed",
        summary=("Knowledge-base indexing was requested " "by an administrator."),
    )

    return {
        "message": "Knowledge base indexed.",
        "result": safe_json_value(result),
    }


@app.get("/api/knowledge/search")
def search_knowledge_base(
    query: str,
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    results = search_knowledge(query)

    return {
        "query": safe_text(query, 500),
        "results": safe_json_value(results),
    }


@app.post("/api/decision-engine/decisions/{decision_id}/approve-pr-review")
@limiter.limit("10/minute")
def approve_pr_review(
    request: Request,
    decision_id: int,
    principal: Principal = Depends(require_roles("reviewer", "admin")),
):
    try:
        result = approve_fix_for_pr_review(decision_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except DecisionStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="The local decision status could not be updated.",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Decision record not found.",
        )

    write_audit(
        principal=principal,
        action="pr_review_status_approved",
        resource_type="decision",
        resource_id=str(decision_id),
        outcome="allowed",
        summary=(
            "A human approved the local status transition "
            "to awaiting_pr_approval. No pull request was created."
        ),
    )
    write_ai_audit_event(
        agent_name="Human Reviewer",
        input_source="Local decision record",
        decision_summary=("Human approved the status transition to PR review."),
        confidence_percent=None,
        action="local_pr_review_approved",
        result=(
            "Decision status changed locally. " "No Azure pull request was created."
        ),
        user_approval="approved",
        actor_subject=principal.subject,
        decision_id=decision_id,
    )

    return result


@app.get("/api/dashboard/infrastructure")
async def dashboard_infrastructure(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    try:
        summary = await get_infrastructure_summary()

        return {
            "available": True,
            "summary": summary,
            "assessment": build_infrastructure_assessment(summary),
        }

    except (httpx.HTTPError, RuntimeError):
        return {
            "available": False,
            "summary": None,
            "assessment": build_infrastructure_assessment({}),
        }


@app.get("/api/dashboard/infrastructure-decision")
def dashboard_infrastructure_decision(
    principal: Principal = Depends(require_roles("viewer", "reviewer", "admin")),
):
    return inspect_infrastructure_state()


@app.post("/api/graph-analyze/{build_id}")
@limiter.limit("3/minute")
def graph_analyze_build(
    request: Request,
    build_id: int,
    principal: Principal = Depends(require_roles("reviewer", "admin", "agent")),
):
    build = get_failed_build_or_raise(build_id)
    raw_logs = read_build_logs_as_text(build_id)

    pipeline_id = build.get("definition", {}).get("id")
    pipeline_configuration: dict[str, Any] = {}

    if pipeline_id:
        pipeline_configuration = azure_get(f"/_apis/pipelines/{pipeline_id}")

    result = pipeline_graph.invoke(
        cast(
            PipelineState,
            {
                "build_id": build_id,
                "pipeline_name": build.get(
                    "definition",
                    {},
                ).get("name", "Unknown"),
                "commit": build.get(
                    "sourceVersion",
                    "Unknown",
                ),
                "environment": "local_review",
                "target_environment": "staging",
                "raw_logs": raw_logs,
                "git_changes": [],
                "pipeline_configuration": safe_json_value(pipeline_configuration),
                "infrastructure_state": inspect_infrastructure_state(),
            },
        )
    )

    source_files = result.get("source_files", {})

    write_audit(
        principal=principal,
        action="failed_build_graph_analyzed",
        resource_type="azure_build",
        resource_id=str(build_id),
        outcome="allowed",
        summary="Safe graph-based failed-build analysis was requested.",
    )

    return {
        "build_id": build_id,
        "workflow_status": safe_text(
            result.get("workflow_status", "completed"),
            200,
        ),
        "decision_status": safe_text(
            result.get("decision_status", "evidence_ready"),
            100,
        ),
        "log_summary": safe_json_value(result.get("log_summary", {})),
        "analysis": safe_json_value(result.get("analysis", {})),
        "recommendation": safe_text(
            result.get("recommendation", ""),
            2000,
        ),
        "fix_proposal": safe_fix_proposal(result.get("fix_proposal", {})),
        "source_files_inspected": (
            [safe_text(file_name, 300) for file_name in source_files.keys()]
            if isinstance(source_files, dict)
            else []
        ),
        "root_cause_graph": safe_json_value(result.get("root_cause_graph", {})),
        "confidence_decision": safe_json_value(result.get("confidence_decision", {})),
    }


@app.post("/api/fixes/create-branch")
def create_ai_fix_branch(
    request: CreateFixBranchRequest,
    principal: Principal = Depends(require_roles("admin")),
):
    write_audit(
        principal=principal,
        action="branch_creation_requested",
        resource_type="azure_build",
        resource_id=str(request.build_id),
        outcome="denied",
        summary=(
            "AI branch creation is permanently disabled. "
            "A human must create branches manually."
        ),
    )

    ensure_automation_is_disabled("AI branch creation")


@app.post("/api/fixes/create-pull-request")
def create_ai_pull_request(
    request: CreatePullRequestRequest,
    principal: Principal = Depends(require_roles("admin")),
):
    write_audit(
        principal=principal,
        action="pull_request_creation_requested",
        resource_type="azure_build",
        resource_id=str(request.build_id),
        outcome="denied",
        summary=(
            "AI pull-request creation is permanently disabled. "
            "A human must create pull requests manually."
        ),
    )

    ensure_automation_is_disabled("AI pull-request creation")


async def monitor_failed_builds() -> None:
    while True:
        try:
            builds = azure_get("/_apis/build/builds?$top=20")

            failed_builds = [
                build
                for build in builds.get("value", [])
                if str(build.get("result", "")).lower() == "failed"
            ]

            print("Read-only monitor found " f"{len(failed_builds)} failed build(s).")

        except Exception as exc:
            print(f"Read-only monitor error: {exc}")

        await asyncio.sleep(60)


@app.on_event("startup")
async def start_monitor() -> None:
    asyncio.create_task(monitor_failed_builds())
