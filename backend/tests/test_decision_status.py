import pytest

from app.services.decision_status import (
    DecisionStatus,
    validate_status_transition,
)


def test_safe_fix_workflow_is_allowed():
    validate_status_transition(
        DecisionStatus.EVIDENCE_READY,
        DecisionStatus.FIX_PROPOSED,
    )

    validate_status_transition(
        DecisionStatus.FIX_PROPOSED,
        DecisionStatus.AWAITING_PR_APPROVAL,
    )

    validate_status_transition(
        DecisionStatus.AWAITING_PR_APPROVAL,
        DecisionStatus.TESTS_PASSED,
    )


def test_unsafe_transition_is_rejected():
    with pytest.raises(ValueError):
        validate_status_transition(
            DecisionStatus.NORMAL_REVIEW,
            DecisionStatus.AWAITING_PR_APPROVAL,
        )
