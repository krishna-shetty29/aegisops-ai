import math
import os
from datetime import datetime, timezone

import httpx

NAMESPACE = "autonomous-ai-devops"
CONTAINER_NAME = "backend"

PROMQL_QUERIES = {
    "cpu_percent": f"""
        100 *
        sum(rate(container_cpu_usage_seconds_total{{
            namespace="{NAMESPACE}",
            container="{CONTAINER_NAME}"
        }}[5m]))
        /
        clamp_min(
            sum(kube_pod_container_resource_limits{{
                namespace="{NAMESPACE}",
                container="{CONTAINER_NAME}",
                resource="cpu",
                unit="core"
            }}),
            0.001
        )
    """,
    "memory_percent": f"""
        100 *
        sum(container_memory_working_set_bytes{{
            namespace="{NAMESPACE}",
            container="{CONTAINER_NAME}"
        }})
        /
        clamp_min(
            sum(kube_pod_container_resource_limits{{
                namespace="{NAMESPACE}",
                container="{CONTAINER_NAME}",
                resource="memory",
                unit="byte"
            }}),
            1
        )
    """,
    "pod_restarts": f"""
        sum(kube_pod_container_status_restarts_total{{
            namespace="{NAMESPACE}"
        }})
    """,
    "error_rate_percent": """
        100 *
        sum(rate(http_requests_total{status=~"5.."}[5m]))
        /
        clamp_min(sum(rate(http_requests_total[5m])), 0.001)
    """,
    "running_pods": f"""
        sum(kube_pod_status_phase{{
            namespace="{NAMESPACE}",
            phase="Running"
        }})
    """,
    "nodes": "count(kube_node_info)",
    "services": f"""
        count(kube_service_info{{
            namespace="{NAMESPACE}"
        }})
    """,
    "alerts_firing": 'count(ALERTS{alertstate="firing"})',
}


async def _query_scalar(
    client: httpx.AsyncClient,
    prometheus_url: str,
    query: str,
) -> float | None:
    response = await client.get(
        f"{prometheus_url}/api/v1/query",
        params={"query": query},
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError("Prometheus did not return a successful query result.")

    results = payload.get("data", {}).get("result", [])

    if not results:
        return None

    value = float(results[0]["value"][1])

    if not math.isfinite(value):
        return None

    return round(value, 2)


async def get_infrastructure_summary() -> dict:
    prometheus_url = os.getenv("PROMETHEUS_URL", "").rstrip("/")

    if not prometheus_url:
        raise RuntimeError("PROMETHEUS_URL is missing.")

    values: dict[str, float | None] = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for metric_name, query in PROMQL_QUERIES.items():
            values[metric_name] = await _query_scalar(
                client,
                prometheus_url,
                query,
            )

    return {
        **values,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
