from app.services.log_sanitizer import redact_sensitive_text


def test_sensitive_values_are_redacted():
    text = (
        "Authorization: Bearer example-token "
        "password=example-password "
        "postgresql://user:password@localhost:5432/demo"
    )

    result = redact_sensitive_text(text)

    assert "example-token" not in result
    assert "example-password" not in result
    assert "[REDACTED]" in result
