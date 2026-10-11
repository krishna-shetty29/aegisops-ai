import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from app.services.ai_audit import write_ai_audit_event

OUTCOMES = {
    "deployed": (
        "human_manual_deployment_completed",
        "A human completed a manual non-production deployment.",
        "Deployment completed through the approved human-controlled process.",
    ),
    "deployment_failed": (
        "human_manual_deployment_failed",
        "A human recorded a failed non-production deployment.",
        "Deployment failed. Human review is required before any rollback.",
    ),
    "rollback_completed": (
        "human_manual_rollback_completed",
        "A human completed a manual non-production rollback.",
        "Rollback was completed through the approved human-controlled process.",
    ),
    "not_run": (
        "human_manual_deployment_not_run",
        "A deployment test was not run.",
        "No approved non-production deployment process was available.",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record a human/manual deployment audit event."
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=["development", "test", "staging"],
    )
    parser.add_argument(
        "--outcome",
        required=True,
        choices=OUTCOMES.keys(),
    )
    parser.add_argument(
        "--azure-build-id",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--actor",
        default="local-developer",
    )

    args = parser.parse_args()

    action, decision_summary, result = OUTCOMES[args.outcome]

    write_ai_audit_event(
        agent_name="Human Deployment Reviewer",
        input_source="Human-controlled Azure DevOps process",
        decision_summary=(f"{decision_summary} Environment: {args.environment}."),
        confidence_percent=None,
        action=action,
        result=result,
        user_approval="approved",
        actor_subject=args.actor,
        azure_build_id=args.azure_build_id,
    )

    print("Manual deployment audit event recorded.")


if __name__ == "__main__":
    main()
