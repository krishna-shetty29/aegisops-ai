from app.services.log_parser import parse_log


def test_parser_finds_and_deduplicates_errors():
    result = parse_log("""
        Starting: Build
        ERROR: package install failed
        ERROR: package install failed
        warning: cache was not restored
        """)

    assert result["error_count"] == 1
    assert result["warning_count"] == 1
    assert "ERROR: package install failed" in result["errors"]


def test_huge_log_context_is_limited():
    huge_log = "\n".join(["normal build output"] * 5000 + ["ERROR: test suite failed"])

    result = parse_log(huge_log)

    assert result["original_line_count"] == 5001
    assert len(result["relevant_context"]) <= 12000
    assert result["relevant_line_count"] <= 120
