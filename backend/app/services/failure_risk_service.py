from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

FEATURE_COLUMNS = [
    "files_changed",
    "changes_count",
    "previous_failures_10",
    "dependency_changes",
    "previous_deployment_failures_10",
]

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BACKEND_DIR / "model_artifacts" / "failure_risk_logistic_regression.joblib"


class FailureRiskModelUnavailable(RuntimeError):
    """Raised when a trained local model is unavailable."""


@lru_cache
def load_model_artifact() -> dict:
    if not MODEL_PATH.exists():
        raise FailureRiskModelUnavailable(
            "The failure-risk model has not been trained yet."
        )

    artifact = joblib.load(MODEL_PATH)

    if "model" not in artifact:
        raise FailureRiskModelUnavailable("The saved model artifact is invalid.")

    return artifact


def predict_failure_risk(features: dict) -> dict:
    artifact = load_model_artifact()
    model = artifact["model"]

    feature_row = {column: int(features[column]) for column in FEATURE_COLUMNS}

    data = pd.DataFrame([feature_row], columns=FEATURE_COLUMNS)

    classes = list(model.classes_)
    failed_class_index = classes.index(1)

    probability = float(model.predict_proba(data)[0][failed_class_index])

    probability_percent = round(probability * 100, 1)
    is_high_risk = probability_percent >= 70

    return {
        "failure_probability_percent": probability_percent,
        "risk_level": "high" if is_high_risk else "normal",
        "model_type": artifact.get(
            "model_type",
            "logistic_regression",
        ),
        "recommended_action": (
            "Review changed dependencies, recent build history, and "
            "test coverage before approval."
            if is_high_risk
            else "Continue with the normal human review process."
        ),
    }
