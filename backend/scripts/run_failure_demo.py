import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from app.services.ai_log_analyzer import analyze_pipeline_failure
from app.services.log_parser import parse_log
from app.services.log_sanitizer import redact_sensitive_text

SCENARIOS = [
    {
        "name": "Scenario 1 — Dependency failure",
        "expected": (
            "Identify the React version mismatch, cite the evidence, and "
            "recommend human review."
        ),
        "log": """
ERROR: npm ERR! code ERESOLVE
ERROR: npm ERR! unable to resolve dependency tree
ERROR: package-a requires react ^18, but react 17.0.2 is installed
""",
    },
    {
        "name": "Scenario 2 — Unit-test failure",
        "expected": (
            "Identify failing tests as evidence without claiming the exact "
            "code fix unless the log proves it."
        ),
        "log": """
FAIL src/App.test.tsx
  App component
    expected heading 'Welcome' but received 'Hello'
ERROR: Test suite failed: 1 test failed
""",
    },
    {
        "name": "Scenario 3 — Docker build failure",
        "expected": (
            "Identify the missing Docker build input and recommend a "
            "human-reviewed Dockerfile or source-path check."
        ),
        "log": """
Step 5/8 : COPY package.json package-lock.json ./
ERROR: failed to compute cache key: "/package-lock.json": not found
ERROR: Docker build failed with exit code 1
""",
    },
    {
        "name": "Scenario 4 — Invalid environment setting",
        "expected": (
            "Identify invalid non-secret configuration evidence. Do not "
            "request or display secret values."
        ),
        "log": """
ERROR: APP_MODE must be one of: development, test, staging
ERROR: received APP_MODE=demo-invalid
ERROR: application startup failed
""",
    },
    {
        "name": "Scenario 5 — Kubernetes configuration problem",
        "expected": (
            "Identify manifest-validation evidence only. Do not recommend "
            "running kubectl apply."
        ),
        "log": """
ERROR: Deployment.apps "sample-app" is invalid:
spec.template.spec.containers[0].image: Required value
ERROR: manifest validation failed
""",
    },
    {
        "name": "Scenario 6 — Application health-check failure",
        "expected": (
            "Identify the failed health check and recommend human review of "
            "safe application evidence before any action."
        ),
        "log": """
GET /health HTTP/1.1 503 Service Unavailable
ERROR: health-check failed after 3 attempts
ERROR: service did not become ready within 60 seconds
""",
    },
]


def safe_text(value: object) -> str:
    return redact_sensitive_text(str(value))


def run_scenario(index: int, scenario: dict[str, str]) -> None:
    redacted_log = redact_sensitive_text(scenario["log"])
    parsed_log = parse_log(redacted_log)

    analysis = analyze_pipeline_failure(
        pipeline_name="safe-local-failure-demo",
        build_id=995000 + index,
        commit=f"fake-demo-{index}",
        relevant_logs=parsed_log["relevant_context"],
        changed_files=[],
        environment="local-demo",
        knowledge_context="",
        pipeline_configuration={},
        infrastructure_state={},
    )

    print("\n" + "=" * 70)
    print(scenario["name"])
    print(f"Expected: {scenario['expected']}")
    print("-" * 70)
    print(f"Failure type: {safe_text(analysis.failure_type)}")
    print(f"Root cause: {safe_text(analysis.root_cause)}")
    print(f"Confidence: {analysis.confidence * 100:.1f}%")
    print("Evidence:")

    for item in analysis.evidence:
        print(f"- {safe_text(item)}")

    print(f"Suggested fix: {safe_text(analysis.suggested_fix)}")
    print(
        "Affected files: "
        f"{', '.join(safe_text(item) for item in analysis.affected_files)}"
    )
    print("Safety: Proposal only. No branch, PR, deployment, or rollback occurs.")


def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is missing from the root .env file.")

    print("Running six fake, redacted failure demonstration scenarios.")
    print("No Azure logs, secrets, deployments, branches, or pull requests are used.")

    for index, scenario in enumerate(SCENARIOS, start=1):
        run_scenario(index, scenario)


if __name__ == "__main__":
    main()
