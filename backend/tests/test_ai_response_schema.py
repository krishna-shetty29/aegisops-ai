import pytest
from pydantic import ValidationError

from app.services.ai_log_analyzer import FailureAnalysis


def test_valid_ai_analysis_schema():
    analysis = FailureAnalysis.model_validate(
        {
            "failure_type": "dependency_error",
            "root_cause": "A package version is unavailable.",
            "evidence": ["ERROR: package version not found"],
            "severity": "high",
            "confidence": 0.94,
            "suggested_fix": "Review and update the dependency version.",
            "affected_files": ["requirements.txt"],
        }
    )

    assert analysis.confidence == 0.94


def test_invalid_ai_confidence_is_rejected():
    with pytest.raises(ValidationError):
        FailureAnalysis.model_validate(
            {
                "failure_type": "dependency_error",
                "root_cause": "Example",
                "evidence": [],
                "severity": "high",
                "confidence": 1.5,
                "suggested_fix": "Example",
                "affected_files": [],
            }
        )
