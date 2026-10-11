import json
import os
import time
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class FailureAnalysis(BaseModel):
    failure_type: str = Field(description="The category of failure.")
    root_cause: str = Field(description="The most likely root cause.")
    evidence: list[str] = Field(description="Log lines that support the conclusion.")
    severity: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]
    confidence: float = Field(
        ge=0,
        le=1,
    )
    suggested_fix: str = Field(description="A safe text-only suggested fix.")
    affected_files: list[str] = Field(
        description="Files likely related to the failure."
    )


def analyze_pipeline_failure(
    pipeline_name: str,
    build_id: int,
    commit: str,
    relevant_logs: str,
    changed_files: list,
    environment: str,
    knowledge_context: str = "",
    pipeline_configuration: dict | None = None,
    infrastructure_state: dict | None = None,
) -> FailureAnalysis:
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is missing from the .env file.")

    model_name = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash-lite",
    )

    client = genai.Client(api_key=gemini_key)

    prompt = f"""
You are an AI DevOps log analyzer.

Analyze only the provided pipeline information.
Do not modify code, run commands, create pull requests,
or make changes to Azure DevOps.

Pipeline name: {pipeline_name}
Build ID: {build_id}
Commit: {commit}
Environment: {environment}

Relevant logs:
{relevant_logs}

Relevant knowledge from previous failures and runbooks:
{knowledge_context}

Changed files:
{json.dumps(changed_files, indent=2)}

Pipeline configuration:
{json.dumps(pipeline_configuration or {}, indent=2)}

Infrastructure state:
{json.dumps(infrastructure_state or {}, indent=2)}

Use the knowledge only as supporting evidence.
Do not claim a previous failure matches unless the current
logs support it.

Safety rules for uncertainty:

- A generic exit code without supporting evidence is insufficient to identify
  a root cause. Set confidence to 0.30 or lower and state that human review
  is required.

- When evidence indicates multiple plausible causes, do not select one as the
  confirmed cause. Set confidence to 0.50 or lower and state the uncertainty.

- When several independent errors appear, list them as evidence. Do not claim
  that one caused the others unless the log directly proves that relationship.

- Every suggested_fix must be advisory only and must state that human review
  is required before any change.

- Never recommend bypassing dependency resolution, disabling tests, skipping
  validation, or using force options such as --legacy-peer-deps.

- Do not create branches, pull requests, deployments, rollbacks, Terraform
  changes, Kubernetes changes, or run commands.

Return only valid JSON matching the required schema.
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FailureAnalysis,
                ),
            )

            response_text = response.text

            if not response_text:
                raise ValueError("The AI provider returned an empty response.")

            return FailureAnalysis.model_validate_json(response_text)

        except Exception:
            if attempt == 2:
                raise

            time.sleep(5)

    raise RuntimeError("Gemini analysis could not be completed.")
