from typing import Any, TypedDict

from app.services.infrastructure_assessment import (
    build_infrastructure_assessment,
)
from app.services.prometheus_service import get_infrastructure_summary


class PipelineState(TypedDict, total=False):
    """
    Safe state shared between pipeline-analysis steps.

    This state contains only approved operational evidence.
    It must never contain secrets, private chain-of-thought,
    full hidden prompts, or automatic action permissions.
    """

    build_id: int
    pipeline_status: str
    pipeline_logs: str
    branch: str
    commit: str

    infrastructure_metrics: dict
    infrastructure_assessment: dict


def approved_metrics(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    """
    Keep only the four approved metrics used for AI evidence.
    """

    return {
        "cpu_percent": raw_metrics.get("cpu_percent"),
        "memory_percent": raw_metrics.get("memory_percent"),
        "pod_restarts": raw_metrics.get("pod_restarts"),
        "error_rate_percent": raw_metrics.get("error_rate_percent"),
    }


def approved_assessment(
    raw_assessment: dict[str, Any],
) -> dict[str, Any]:
    """
    Keep only concise, reviewable AI-facing fields.
    """

    return {
        "decision": raw_assessment.get(
            "decision",
            "infrastructure_assessment_unavailable",
        ),
        "confidence": raw_assessment.get("confidence", 0.0),
        "summary": raw_assessment.get(
            "summary",
            "No infrastructure assessment is available.",
        ),
        "evidence": raw_assessment.get("evidence", []),
        "recommended_action": raw_assessment.get(
            "recommended_action",
            "Review monitoring data and deployment logs before making changes.",
        ),
    }


async def collect_infrastructure_evidence(
    state: PipelineState,
) -> dict[str, Any]:
    """
    LangGraph-compatible pipeline node.

    Call this only for a failed pipeline, before AI analysis.
    It collects approved Prometheus-derived evidence through the
    restricted service layer; it never queries Prometheus directly
    from React or exposes hidden reasoning.
    """

    try:
        raw_metrics = await get_infrastructure_summary()
        metrics = approved_metrics(raw_metrics)

        raw_assessment = build_infrastructure_assessment(raw_metrics)
        assessment = approved_assessment(raw_assessment)

        return {
            "infrastructure_metrics": metrics,
            "infrastructure_assessment": assessment,
        }

    except Exception:
        # Prometheus being unavailable must not crash pipeline analysis.
        # Do not include internal errors, URLs, credentials, or stack traces.
        return {
            "infrastructure_metrics": {},
            "infrastructure_assessment": {
                "decision": "infrastructure_metrics_unavailable",
                "confidence": 0.0,
                "summary": (
                    "Infrastructure metrics could not be collected for this "
                    "pipeline failure."
                ),
                "evidence": [],
                "recommended_action": (
                    "Check Prometheus target health and review deployment logs "
                    "before proposing a fix."
                ),
            },
        }


def build_safe_ai_evidence(state: PipelineState) -> dict[str, Any]:
    """
    The only infrastructure information that may be supplied to an AI prompt.
    """

    return {
        "infrastructure_metrics": state.get(
            "infrastructure_metrics",
            {},
        ),
        "infrastructure_assessment": state.get(
            "infrastructure_assessment",
            {},
        ),
    }
