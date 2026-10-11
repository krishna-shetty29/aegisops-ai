from fastapi import HTTPException, status


def ensure_automation_is_disabled(action: str) -> None:
    """
    Hard safety boundary.

    This project never allows the AI/API path to create branches,
    create pull requests, deploy, roll back, run Terraform, or
    mutate Kubernetes resources.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"{action} is disabled. Human approval and manual " "action are required."
        ),
    )
