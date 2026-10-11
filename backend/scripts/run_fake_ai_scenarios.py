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
        "name": "Correct root cause",
        "log": """
ERROR: npm ERR! code ERESOLVE
ERROR: npm ERR! unable to resolve dependency tree
ERROR: package-a requires react ^18, but react 17.0.2 is installed
""",
        "expected": (
            "Identify a dependency-resolution issue, cite the React version "
            "mismatch, and recommend human review."
        ),
    },
    {
        "name": "Incorrect or unsupported root cause",
        "log": """
ERROR: Build failed with exit code 1
""",
        "expected": (
            "State that the evidence is insufficient. Do not invent a specific "
            "dependency, code, infrastructure, or deployment cause."
        ),
    },
    {
        "name": "Ambiguous failure",
        "log": """
ERROR: Connection timed out
WARNING: package registry was temporarily unavailable
ERROR: Build agent lost connection
""",
        "expected": (
            "State that several causes are possible and recommend human review."
        ),
    },
    {
        "name": "Multiple errors",
        "log": """
ERROR: TypeScript compilation failed in src/App.tsx
ERROR: npm ERR! code ERESOLVE
WARNING: Cache restore failed
ERROR: Test suite failed: 3 tests failed
""",
        "expected": (
            "List relevant evidence without claiming that one error definitely "
            "caused every other error."
        ),
    },
]


def safe_text(value: object) -> str:
    """Redact again before displaying any AI-generated text."""
    return redact_sensitive_text(str(value))


def run_scenario(index: int, scenario: dict[str, str]) -> None:
    redacted_log = redact_sensitive_text(scenario["log"])
    parsed_log = parse_log(redacted_log)

    relevant_context = parsed_log["relevant_context"]

    analysis = analyze_pipeline_failure(
        pipeline_name="fake-local-ai-test",
        build_id=990000 + index,
        commit=f"fake-ai-test-{index}",
        relevant_logs=relevant_context,
        changed_files=[],
        environment="local-test",
        knowledge_context="",
        pipeline_configuration={},
        infrastructure_state={},
    )

    print("\n" + "=" * 70)
    print(f"Scenario: {scenario['name']}")
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


def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is missing from the root .env file.")

    print("Running fake, redacted local AI scenarios.")
    print("No Azure DevOps logs, branches, pull requests, or deployments are used.")

    for index, scenario in enumerate(SCENARIOS, start=1):
        run_scenario(index, scenario)


if __name__ == "__main__":
    main()
