const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function getJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

export async function getBuilds() {
  const data = await getJson("/api/builds");

  if (Array.isArray(data)) {
    return data;
  }

  return data.builds || data.value || data.items || [];
}

export async function getHealth() {
  return getJson("/health");
}

export async function getInfrastructureSummary() {
  return getJson("/api/dashboard/infrastructure");
}

export async function getInfrastructureDecision() {
  return getJson("/api/dashboard/infrastructure-decision");
}
export async function getFailureRisk(features) {
  const response = await fetch(
    `${API_BASE_URL}/api/predictions/failure-risk`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(features),
    }
  );

  if (!response.ok) {
    throw new Error(`Prediction request failed: ${response.status}`);
  }

  return response.json();
}
export async function analyzeFailedBuild(buildId) {
  const response = await fetch(
    `${API_BASE_URL}/api/graph-analyze/${buildId}`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    throw new Error(`Build analysis failed: ${response.status}`);
  }

  return response.json();
}
export async function getDecisionRecords() {
  const response = await fetch(
    `${"http://127.0.0.1:8000"}/api/decision-engine/decisions`
  );

  if (!response.ok) {
    throw new Error("Could not load decision records.");
  }

  return response.json();
}