import base64
import os
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import requests

API_VERSION = "7.1"
ZERO_SHA = "0" * 40


def _settings() -> tuple[str, str, str, str]:
    organization = os.getenv("AZURE_DEVOPS_ORGANIZATION")
    project = os.getenv("AZURE_DEVOPS_PROJECT")
    repository = os.getenv("AZURE_DEVOPS_REPOSITORY")
    pat = os.getenv("AZURE_DEVOPS_PAT")

    if not all([organization, project, repository, pat]):
        raise ValueError("Azure DevOps settings are missing from the .env file.")

    return (
        str(organization),
        str(project),
        str(repository),
        str(pat),
    )


def _azure_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    organization, project, _, pat = _settings()

    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")

    url = f"https://dev.azure.com/{organization}/{project}" f"{path}"

    response = requests.request(
        method=method,
        url=url,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )

    if not response.ok:
        raise RuntimeError(
            f"Azure DevOps request failed: " f"{response.status_code} {response.text}"
        )

    return response.json()


def _safe_file_path(file_path: str) -> str:
    normalized = "/" + file_path.replace("\\", "/").lstrip("/")

    blocked_names = {
        ".env",
        ".git",
        ".venv",
        "__pycache__",
    }

    path_parts = set(part.lower() for part in PurePosixPath(normalized).parts)

    if path_parts.intersection(blocked_names):
        raise ValueError("This file path is blocked for safety.")

    allowed_extensions = {
        ".py",
        ".txt",
        ".yml",
        ".yaml",
        ".json",
        ".md",
    }

    file_name = PurePosixPath(normalized).name
    suffix = PurePosixPath(normalized).suffix.lower()

    if suffix not in allowed_extensions and file_name not in {
        "Dockerfile",
        "docker-compose.yml",
    }:
        raise ValueError("Only approved source and configuration files can change.")

    return normalized


def get_repository_id() -> str:
    _, _, repository, _ = _settings()

    data = _azure_request(
        "GET",
        f"/_apis/git/repositories/{quote(repository)}" f"?api-version={API_VERSION}",
    )

    return data["id"]


def get_main_commit_sha(repository_id: str) -> str:
    data = _azure_request(
        "GET",
        f"/_apis/git/repositories/{repository_id}/refs"
        f"?filter=heads/main&api-version={API_VERSION}",
    )

    refs = data.get("value", [])

    if not refs:
        raise ValueError("The main branch was not found.")

    return refs[0]["objectId"]
