from typing import Any, NotRequired, Required, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.ai_fix_generator import FixProposal, generate_fix_proposal
from app.services.ai_log_analyzer import FailureAnalysis, analyze_pipeline_failure
from app.services.confidence_policy import make_confidence_decision
from app.services.log_parser import parse_log
from app.services.rag_service import format_knowledge_context, search_knowledge
from app.services.root_cause_evidence import build_root_cause_graph
from app.services.source_inspector import read_relevant_source_files


class PipelineState(TypedDict, total=False):
    # Required input and graph-produced values.
    build_id: Required[int]
    pipeline_name: Required[str]
    commit: Required[str]
    environment: Required[str]
    raw_logs: Required[str]
    relevant_logs: Required[str]
    analysis: Required[dict[str, Any]]

    # Optional safe supporting values.
    target_environment: NotRequired[str]
    confidence_decision: NotRequired[dict[str, Any]]
    git_changes: NotRequired[list[str]]
    pipeline_configuration: NotRequired[dict[str, Any]]
    infrastructure_state: NotRequired[dict[str, Any]]
    root_cause_graph: NotRequired[dict[str, Any]]
    log_summary: NotRequired[dict[str, Any]]
    source_files: NotRequired[dict[str, str]]
    fix_proposal: NotRequired[dict[str, Any]]
    recommendation: NotRequired[str]
    workflow_status: NotRequired[str]
    decision_status: NotRequired[str]


def supervisor(state: PipelineState) -> dict[str, Any]:
    return {
        "workflow_status": "Pipeline failure received. Starting safe analysis.",
        "decision_status": "build_failed",
    }


def log_analyzer(state: PipelineState) -> dict[str, Any]:
    parsed_log = parse_log(state["raw_logs"])

    return {
        "relevant_logs": str(parsed_log.get("relevant_context", ""))[:8000],
        "log_summary": {
            "error_count": parsed_log.get("error_count", 0),
            "warning_count": parsed_log.get("warning_count", 0),
            "errors": parsed_log.get("errors", []),
            "warnings": parsed_log.get("warnings", []),
        },
        "workflow_status": "Evidence collected from the failed build.",
        "decision_status": "evidence_ready",
    }


def root_cause_analyzer(state: PipelineState) -> dict[str, Any]:
    knowledge_matches = search_knowledge(state["relevant_logs"][:4000])
    knowledge_context = format_knowledge_context(knowledge_matches)

    analysis_model: FailureAnalysis = analyze_pipeline_failure(
        pipeline_name=state["pipeline_name"],
        build_id=state["build_id"],
        commit=state["commit"],
        relevant_logs=state["relevant_logs"],
        changed_files=state.get("git_changes", []),
        environment=state["environment"],
        knowledge_context=knowledge_context,
        pipeline_configuration=state.get("pipeline_configuration", {}),
        infrastructure_state=state.get("infrastructure_state", {}),
    )

    analysis: dict[str, Any] = analysis_model.model_dump()

    root_cause_graph = build_root_cause_graph(
        analysis=analysis,
        changed_files=state.get("git_changes", []),
        pipeline_configuration=state.get("pipeline_configuration", {}),
        previous_failures=knowledge_matches,
        infrastructure_state=state.get("infrastructure_state", {}),
    )

    return {
        "analysis": analysis,
        "root_cause_graph": root_cause_graph,
        "workflow_status": "Root-cause evidence is ready for review.",
        "decision_status": "evidence_ready",
    }


def confidence_decision_agent(state: PipelineState) -> dict[str, Any]:
    analysis = state["analysis"]

    decision = make_confidence_decision(
        confidence=float(analysis.get("confidence", 0.0)),
        target_environment=state.get("target_environment", "staging"),
    )

    return {
        "confidence_decision": decision,
        "workflow_status": str(decision.get("message", "Human review is required.")),
        "decision_status": "evidence_ready",
    }


def fix_recommendation(state: PipelineState):
    analysis = state["analysis"]

    affected_files = analysis.get(
        "affected_files",
        [],
    )

    changed_files = state.get(
        "git_changes",
        [],
    )

    files_to_inspect = list(dict.fromkeys(affected_files + changed_files))

    source_files = read_relevant_source_files(files_to_inspect)

    previous_matches = search_knowledge(
        f"{analysis.get('root_cause', '')} " f"{analysis.get('suggested_fix', '')}"
    )

    previous_fixes = format_knowledge_context(previous_matches)

    fix_proposal = generate_fix_proposal(
        root_cause=analysis.get(
            "root_cause",
            "Unknown root cause",
        ),
        suggested_fix=analysis.get(
            "suggested_fix",
            "",
        ),
        relevant_source_files=source_files,
        pipeline_configuration=state.get(
            "pipeline_configuration",
            {},
        ),
        previous_fixes=previous_fixes,
    )

    if hasattr(fix_proposal, "model_dump"):
        fix_proposal = fix_proposal.model_dump()

    has_proposed_change = any(
        str(fix_proposal.get(field, "")).strip()
        for field in (
            "modified_file",
            "patch",
            "replacement_content",
        )
    )

    decision_status = (
        "awaiting_pr_approval" if has_proposed_change else "evidence_ready"
    )

    return {
        "source_files": source_files,
        "fix_proposal": fix_proposal,
        "recommendation": fix_proposal.get(
            "explanation",
            "No fix recommendation was generated.",
        ),
        "decision_status": decision_status,
        "workflow_status": (
            "Fix proposal ready for human review. " "No code was changed."
            if has_proposed_change
            else "Evidence is ready. No code change was proposed."
        ),
    }


graph_builder = StateGraph(PipelineState)

graph_builder.add_node("supervisor", supervisor)
graph_builder.add_node("log_analyzer", log_analyzer)
graph_builder.add_node("root_cause_analyzer", root_cause_analyzer)
graph_builder.add_node(
    "confidence_decision",
    confidence_decision_agent,
)
graph_builder.add_node("fix_recommendation", fix_recommendation)

graph_builder.add_edge(START, "supervisor")
graph_builder.add_edge("supervisor", "log_analyzer")
graph_builder.add_edge("log_analyzer", "root_cause_analyzer")
graph_builder.add_edge(
    "root_cause_analyzer",
    "confidence_decision",
)
graph_builder.add_edge(
    "confidence_decision",
    "fix_recommendation",
)
graph_builder.add_edge("fix_recommendation", END)

pipeline_graph = graph_builder.compile()
