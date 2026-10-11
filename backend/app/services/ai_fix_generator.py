import json
import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class FixProposal(BaseModel):
    modified_file: str = Field(
        description=(
            "The single file that should be changed. "
            "Use an empty string when no code change is needed."
        )
    )

    patch: str = Field(
        description=(
            "A human-readable unified-diff-style patch. "
            "Use an empty string when no code change is needed."
        )
    )

    replacement_content: str = Field(
        description=(
            "The complete new content for modified_file. "
            "Use an empty string when no code change is needed."
        )
    )

    explanation: str = Field(
        description="A clear explanation of why this proposed fix helps."
    )

    tests_required: list[str] = Field(
        description="Tests or checks a human should run after the change."
    )

    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence in this proposed fix from 0 to 1.",
    )

    requires_human_approval: bool = Field(
        default=True,
        description=(
            "Always true. A human must review before any branch, "
            "pull request, merge, or deployment."
        ),
    )


def generate_fix_proposal(
    root_cause: str,
    suggested_fix: str,
    relevant_source_files: dict[str, str],
    pipeline_configuration: dict | None = None,
    previous_fixes: str = "",
) -> FixProposal:
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is missing from the .env file.")

    model_name = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )

    client = genai.Client(api_key=gemini_key)

    prompt = f"""
You are an AI DevOps fix-proposal assistant.

You may analyze the provided evidence and source files.
You must not modify files, run commands, create branches,
create Pull Requests, merge code, deploy software,
or change Azure DevOps settings.

Root cause:
{root_cause}

Suggested fix:
{suggested_fix}

Relevant source files:
{json.dumps(relevant_source_files, indent=2)}

Pipeline configuration:
{json.dumps(pipeline_configuration or {}, indent=2)}

Relevant previous fixes and runbooks:
{previous_fixes}

Rules:
1. Propose a change only when the provided source files support it.
2. Modify at most one file.
3. Never propose changes to .env, secrets, credentials, or tokens.
4. Never propose changes inside .git, .venv, or __pycache__.
5. Do not invent source code that is not supported by the supplied files.
6. If the failure was intentionally forced or no code change is needed,
   return empty strings for modified_file, patch, and replacement_content.
7. Always set requires_human_approval to true.

If a file must change, return the complete replacement content of that
single file in replacement_content. Do not return only a diff.

If no source-code change is required, set patch and replacement_content
to empty strings.

Return only valid JSON that matches the required schema.
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FixProposal,
                ),
            )

            response_text = response.text

            if not response_text:
                raise ValueError("Gemini returned an empty fix-proposal response.")

            proposal = FixProposal.model_validate_json(response_text)

            # Human approval is always required.
            return proposal.model_copy(
                update={
                    "requires_human_approval": True,
                }
            )

        except Exception as error:
            if attempt == 2:
                raise error

            time.sleep(5)

    raise RuntimeError("Unable to generate a fix proposal.")
