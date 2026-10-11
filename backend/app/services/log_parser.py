import re


def is_noise(line: str) -> bool:
    lowered = line.lower().strip()

    noise_starts = (
        "##[debug]",
        "starting:",
        "finishing:",
        "agent name:",
        "agent machine name:",
        "current operating system:",
        "download task:",
        "##[section]",
    )

    return lowered.startswith(noise_starts)


def is_error(line: str) -> bool:
    lowered = line.lower()

    error_signals = (
        "##[error]",
        "error:",
        "exception",
        "traceback",
        "failed",
        "exit code",
        "exited with code",
    )

    return any(signal in lowered for signal in error_signals)


def is_warning(line: str) -> bool:
    lowered = line.lower()

    return "##[warning]" in lowered or "warning:" in lowered


def normalize_error(line: str) -> str:
    # Makes similar messages group together.
    return re.sub(r"\d+", "#", line.lower().strip())


def parse_log(log_text: str) -> dict:
    lines = log_text.splitlines()

    errors = []
    warnings = []
    relevant_context = []
    seen_errors = set()

    for index, line in enumerate(lines):
        if is_noise(line):
            continue

        if is_error(line):
            normalised = normalize_error(line)

            # Do not keep the same error repeatedly.
            if normalised in seen_errors:
                continue

            seen_errors.add(normalised)
            errors.append(line.strip())

            # Keep 3 lines before and 3 lines after an error.
            start = max(0, index - 3)
            end = min(len(lines), index + 4)

            for context_line in lines[start:end]:
                if not is_noise(context_line):
                    relevant_context.append(context_line)

        elif is_warning(line):
            warnings.append(line.strip())

    # If no error was found, keep the final useful lines.
    if not relevant_context:
        relevant_context = [
            line for line in lines[-50:]
            if not is_noise(line)
        ]

    # Limit output so huge logs are never sent to an LLM.
    relevant_context = relevant_context[:120]
    relevant_text = "\n".join(relevant_context)[:12000]

    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:20],
        "warnings": warnings[:20],
        "relevant_context": relevant_text,
        "original_line_count": len(lines),
        "relevant_line_count": len(relevant_context),
    }