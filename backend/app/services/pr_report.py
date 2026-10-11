def build_pr_title(build_id: int, root_cause: str) -> str:
    short_cause = root_cause.strip()[:70]

    return f"AI Fix #{build_id}: {short_cause}"


def build_pr_description(
    build_id: int,
    pipeline_name: str,
    root_cause: str,
    evidence: list[str],
    proposed_solution: str,
    changed_files: list[str],
    tests_performed: list[str],
    confidence: float,
) -> str:
    evidence_text = "\n".join(
        f"- {line}" for line in evidence
    ) or "- No evidence supplied."

    files_text = "\n".join(
        f"- `{file_name}`" for file_name in changed_files
    ) or "- No files changed."

    tests_text = "\n".join(
        f"- {test}" for test in tests_performed
    ) or "- No tests recorded."

    confidence_percent = round(confidence * 100)

    return f"""## Problem

Azure Pipeline build **{build_id}** failed.

Pipeline: `{pipeline_name}`

## Root cause

{root_cause}

## Evidence

{evidence_text}

## Proposed solution

{proposed_solution}

## Files changed

{files_text}

## Tests performed

{tests_text}

## AI confidence

{confidence_percent}%

---

This Pull Request was prepared by the AI DevOps Engineer.
A human must review the change and merge it manually.
"""