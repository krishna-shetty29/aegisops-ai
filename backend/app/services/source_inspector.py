from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ALLOWED_SUFFIXES = {
    ".py",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".md",
}

ALLOWED_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
}

BLOCKED_PARTS = {
    ".env",
    ".git",
    ".venv",
    "__pycache__",
}


def is_safe_source_path(file_path: str):
    clean_path = file_path.replace("\\", "/").lstrip("/")

    path_parts = clean_path.split("/")

    if any(part in BLOCKED_PARTS for part in path_parts):
        return False

    file_name = Path(clean_path).name

    if file_name in ALLOWED_FILENAMES:
        return True

    return Path(file_name).suffix.lower() in ALLOWED_SUFFIXES


def read_relevant_source_files(file_paths: list[str]):
    source_files = {}

    for file_path in file_paths:
        if not is_safe_source_path(file_path):
            continue

        clean_path = file_path.replace("\\", "/").lstrip("/")

        possible_locations = [
            PROJECT_ROOT / clean_path,
            PROJECT_ROOT / "sample-app" / clean_path,
        ]

        for full_path in possible_locations:
            if not full_path.is_file():
                continue

            source_files[clean_path] = full_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )[:12000]

            break

    return source_files