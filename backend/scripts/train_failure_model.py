import json
import os
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from psycopg import connect
from psycopg.rows import dict_row
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "files_changed",
    "changes_count",
    "previous_failures_10",
    "dependency_changes",
    "previous_deployment_failures_10",
]

ROOT_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT_DIR / "backend" / "model_artifacts"
MODEL_PATH = MODEL_DIR / "failure_risk_logistic_regression.joblib"
METRICS_PATH = MODEL_DIR / "failure_risk_metrics.json"


def load_training_data(database_url: str) -> pd.DataFrame:
    query = """
        SELECT
            azure_build_id,
            completed_at,
            files_changed,
            changes_count,
            previous_failures_10,
            dependency_changes,
            previous_deployment_failures_10,
            failed
        FROM pipeline_training_examples
        ORDER BY completed_at ASC, azure_build_id ASC;
    """

    with connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return pd.DataFrame(rows)


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from the root .env file.")

    data = load_training_data(database_url)

    if len(data) < 30:
        raise RuntimeError("At least 30 completed pipeline examples are required.")

    data["failed"] = data["failed"].astype(int)

    for column in FEATURE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    split_index = int(len(data) * 0.8)
    training_data = data.iloc[:split_index].copy()
    test_data = data.iloc[split_index:].copy()

    if training_data["failed"].nunique() < 2:
        raise RuntimeError(
            "The training portion must contain both successful and failed builds."
        )

    x_train = training_data[FEATURE_COLUMNS]
    y_train = training_data["failed"]

    x_test = test_data[FEATURE_COLUMNS]
    y_test = test_data["failed"]

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    random_state=42,
                    max_iter=1000,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    model.fit(x_train, y_train)

    predicted_labels = model.predict(x_test)
    predicted_probabilities = model.predict_proba(x_test)[:, 1]

    metrics = {
        "model_type": "logistic_regression",
        "training_rows": int(len(training_data)),
        "held_out_rows": int(len(test_data)),
        "accuracy": round(float(accuracy_score(y_test, predicted_labels)), 4),
        "roc_auc": None,
        "feature_columns": FEATURE_COLUMNS,
        "evaluation_method": "newest_20_percent_held_out",
    }

    if y_test.nunique() == 2:
        metrics["roc_auc"] = round(
            float(roc_auc_score(y_test, predicted_probabilities)),
            4,
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model": model,
        "model_type": "logistic_regression",
        "feature_columns": FEATURE_COLUMNS,
        "review_threshold_percent": 70,
        "metrics": metrics,
    }

    joblib.dump(artifact, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("Training completed.")
    print(json.dumps(metrics, indent=2))
    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
