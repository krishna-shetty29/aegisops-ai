from enum import Enum


class AgentName(str, Enum):
    PIPELINE = "pipeline_agent"
    LOG = "log_agent"
    ROOT_CAUSE = "root_cause_agent"
    FIX = "fix_agent"
    VALIDATION = "validation_agent"
    DEPLOYMENT = "deployment_agent"
    ROLLBACK = "rollback_agent"


AGENT_PERMISSIONS = {
    AgentName.PIPELINE: {
        "read_pipeline_information",
        "read_build_status",
        "read_pipeline_configuration",
    },
    AgentName.LOG: {
        "read_logs",
        "extract_errors",
        "group_errors",
    },
    AgentName.ROOT_CAUSE: {
        "analyze_evidence",
        "identify_root_cause",
        "assign_confidence",
    },
    AgentName.FIX: {
        "inspect_source_files",
        "generate_proposed_patch",
    },
    AgentName.VALIDATION: {
        "run_tests",
        "check_build",
        "check_health",
    },
    AgentName.DEPLOYMENT: {
        "deploy_to_test_environment",
    },
    AgentName.ROLLBACK: {
        "restore_known_good_deployment",
    },
}


def is_allowed(agent_name: AgentName, action: str) -> bool:
    """Return True only when an agent has permission for an action."""

    return action in AGENT_PERMISSIONS.get(agent_name, set())


def require_permission(agent_name: AgentName, action: str):
    """Stop an agent when it tries an action it is not allowed to perform."""

    if not is_allowed(agent_name, action):
        raise PermissionError(
            f"{agent_name.value} is not allowed to perform: {action}"
        )