from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def inspect_infrastructure_state():
    files_to_check = [
        "sample-app/Dockerfile",
        "docker-compose.yml",
        "kubernetes/deployment.yaml",
        "kubernetes/service.yaml",
        "terraform",
    ]

    results = []

    for relative_path in files_to_check:
        full_path = PROJECT_ROOT / relative_path

        results.append(
            {
                "path": relative_path,
                "exists": full_path.exists(),
                "is_directory": full_path.is_dir(),
            }
        )

    return {
        "checked_files": results,
        "message": (
            "Local infrastructure file presence was checked. "
            "No infrastructure was changed."
        ),
    }


def build_root_cause_graph(
    analysis,
    changed_files,
    pipeline_configuration,
    previous_failures,
    infrastructure_state,
):
    nodes = [
        {
            "id": "pipeline_failure",
            "label": "Pipeline Failure",
            "type": "event",
        },
        {
            "id": "logs",
            "label": "Relevant Log Errors",
            "type": "evidence",
        },
        {
            "id": "git_changes",
            "label": f"{len(changed_files)} Changed File(s)",
            "type": "evidence",
        },
        {
            "id": "pipeline_config",
            "label": "Pipeline Configuration",
            "type": "evidence",
        },
        {
            "id": "previous_failures",
            "label": (
                f"{len(previous_failures)} Similar "
                "Knowledge Match(es)"
            ),
            "type": "evidence",
        },
        {
            "id": "infrastructure",
            "label": "Infrastructure State",
            "type": "evidence",
        },
        {
            "id": "root_cause",
            "label": analysis.get(
                "root_cause",
                "Root cause not identified",
            ),
            "type": "root_cause",
        },
    ]

    edges = [
        {
            "source": "pipeline_failure",
            "target": "logs",
        },
        {
            "source": "logs",
            "target": "git_changes",
        },
        {
            "source": "git_changes",
            "target": "pipeline_config",
        },
        {
            "source": "pipeline_config",
            "target": "previous_failures",
        },
        {
            "source": "previous_failures",
            "target": "infrastructure",
        },
        {
            "source": "infrastructure",
            "target": "root_cause",
        },
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "evidence": {
            "changed_files": changed_files,
            "pipeline_configuration": pipeline_configuration,
            "previous_failures": previous_failures,
            "infrastructure_state": infrastructure_state,
        },
    }