import re

SENSITIVE_PATTERNS = [
    (
        r"(?i)(authorization:\s*bearer\s+)[^\s]+",
        r"\1[REDACTED]",
    ),
    (
        r"(?i)((?:api[_-]?key|token|password|secret|pat)\s*[=:]\s*)[^\s'\";]+",
        r"\1[REDACTED]",
    ),
    (
        r"(?i)(postgres(?:ql)?://)[^\s]+",
        r"\1[REDACTED]",
    ),
    (
        r"(?i)(https://[^/\s:@]+:)[^@/\s]+@",
        r"\1[REDACTED]@",
    ),
]


def redact_sensitive_text(text: str) -> str:
    sanitized_text = str(text or "")

    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized_text = re.sub(
            pattern,
            replacement,
            sanitized_text,
        )

    return sanitized_text
