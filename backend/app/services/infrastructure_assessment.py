def build_infrastructure_assessment(metrics: dict) -> dict:
    evidence: list[str] = []
    infrastructure_signals = 0

    cpu_percent = metrics.get("cpu_percent")
    memory_percent = metrics.get("memory_percent")
    pod_restarts = metrics.get("pod_restarts")
    error_rate_percent = metrics.get("error_rate_percent")

    if cpu_percent is not None and cpu_percent >= 85:
        evidence.append(f"CPU usage is {cpu_percent}%.")
        infrastructure_signals += 1

    if memory_percent is not None and memory_percent >= 85:
        evidence.append(f"Memory usage is {memory_percent}%.")
        infrastructure_signals += 1

    if pod_restarts is not None and pod_restarts >= 3:
        evidence.append(f"Pod restart count is {pod_restarts}.")
        infrastructure_signals += 1

    if error_rate_percent is not None and error_rate_percent >= 5:
        evidence.append(f"HTTP error rate is {error_rate_percent}%.")
        infrastructure_signals += 1

    if infrastructure_signals >= 2:
        return {
            "decision": "likely_infrastructure_related",
            "confidence": 0.82,
            "summary": (
                "Multiple infrastructure-pressure signals were detected. "
                "Review Kubernetes resources and deployment logs before proposing a code fix."
            ),
            "evidence": evidence,
            "recommended_action": (
                "Review memory and CPU limits, pod logs, restart history, "
                "and deployment health before creating an AI fix proposal."
            ),
        }

    return {
        "decision": "no_strong_infrastructure_signal",
        "confidence": 0.4,
        "summary": (
            "Current selected metrics do not show strong evidence of an "
            "infrastructure-related failure."
        ),
        "evidence": evidence or ["No selected metric exceeded the warning threshold."],
        "recommended_action": (
            "Continue investigating pipeline logs, dependency errors, and source-code evidence."
        ),
    }
