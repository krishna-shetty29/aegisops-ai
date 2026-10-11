def make_confidence_decision(
    confidence: float,
    target_environment: str = "staging",
):
    if confidence < 0 or confidence > 1:
        raise ValueError("Confidence must be between 0 and 1.")

    if target_environment.lower() == "production":
        return {
            "decision": "production_changes_blocked",
            "confidence": confidence,
            "requires_human_review": True,
            "can_apply_fix": False,
            "message": (
                "Production changes are disabled. " "Human approval is required."
            ),
        }

    if confidence < 0.70:
        return {
            "decision": "human_review_required",
            "confidence": confidence,
            "requires_human_review": True,
            "can_apply_fix": False,
            "message": (
                "Confidence is below 70%. " "A human must review the evidence."
            ),
        }

    return {
        "decision": "proposal_only",
        "confidence": confidence,
        "requires_human_review": True,
        "can_apply_fix": False,
        "message": (
            "A proposed fix is ready for human review. "
            "No branch, pull request, merge, deployment, "
            "or rollback will occur automatically."
        ),
    }
