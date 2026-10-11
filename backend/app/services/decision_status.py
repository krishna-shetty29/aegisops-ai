from enum import Enum


class DecisionStatus(str, Enum):
    RECEIVED = "received"
    PREDICTED = "predicted"
    NORMAL_REVIEW = "normal_review"
    HUMAN_REVIEW_RECOMMENDED = "human_review_recommended"
    BUILD_RUNNING = "build_running"
    BUILD_SUCCEEDED = "build_succeeded"
    BUILD_FAILED = "build_failed"
    EVIDENCE_READY = "evidence_ready"
    FIX_PROPOSED = "fix_proposed"
    AWAITING_PR_APPROVAL = "awaiting_pr_approval"
    TESTS_PASSED = "tests_passed"
    TESTS_FAILED = "tests_failed"
    CLOSED = "closed"


ALLOWED_TRANSITIONS = {
    DecisionStatus.RECEIVED: {
        DecisionStatus.PREDICTED,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.PREDICTED: {
        DecisionStatus.NORMAL_REVIEW,
        DecisionStatus.HUMAN_REVIEW_RECOMMENDED,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.NORMAL_REVIEW: {
        DecisionStatus.BUILD_RUNNING,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.HUMAN_REVIEW_RECOMMENDED: {
        DecisionStatus.BUILD_RUNNING,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.BUILD_RUNNING: {
        DecisionStatus.BUILD_SUCCEEDED,
        DecisionStatus.BUILD_FAILED,
    },
    DecisionStatus.BUILD_SUCCEEDED: {
        DecisionStatus.CLOSED,
    },
    DecisionStatus.BUILD_FAILED: {
        DecisionStatus.EVIDENCE_READY,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.EVIDENCE_READY: {
        DecisionStatus.FIX_PROPOSED,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.FIX_PROPOSED: {
        DecisionStatus.AWAITING_PR_APPROVAL,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.AWAITING_PR_APPROVAL: {
        DecisionStatus.TESTS_PASSED,
        DecisionStatus.TESTS_FAILED,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.TESTS_PASSED: {
        DecisionStatus.CLOSED,
    },
    DecisionStatus.TESTS_FAILED: {
        DecisionStatus.EVIDENCE_READY,
        DecisionStatus.FIX_PROPOSED,
        DecisionStatus.CLOSED,
    },
    DecisionStatus.CLOSED: set(),
}


def validate_status_transition(
    current_status: DecisionStatus,
    next_status: DecisionStatus,
) -> None:
    allowed_next_statuses = ALLOWED_TRANSITIONS[current_status]

    if next_status not in allowed_next_statuses:
        raise ValueError(
            f"Unsafe status transition: "
            f"{current_status.value} -> {next_status.value}"
        )
