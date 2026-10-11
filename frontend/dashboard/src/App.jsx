import { useEffect, useMemo, useState } from "react";

import {
  analyzeFailedBuild,
  getBuilds,
  getDecisionRecords,
  getInfrastructureDecision,
  getInfrastructureSummary,
} from "./api";

import "./App.css";

const pages = [
  "Overview",
  "Pipelines",
  "Failure Details",
  "AI Decision",
  "Pull Requests",
  "Deployments",
  "Infrastructure",
];

function valueOrUnavailable(value) {
  return value === null || value === undefined
    ? "Metric unavailable"
    : value;
}

function percentOrUnavailable(value) {
  return value === null || value === undefined
    ? "Metric unavailable"
    : `${Number(value).toFixed(1)}%`;
}

function getBuildStatus(build) {
  return String(build.result || build.status || build.state || "Unknown");
}

function displayDecisionStatus(value) {
  if (!value) {
    return "Unavailable";
  }

  return String(value).replaceAll("_", " ");
}

function StatusBadge({ value }) {
  const status = String(value || "Unknown");
  const normalized = status.toLowerCase();

  let className = "status unknown";

  if (
    normalized.includes("success") ||
    normalized.includes("healthy") ||
    normalized.includes("running") ||
    normalized.includes("pass")
  ) {
    className = "status success";
  }

  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("unhealthy")
  ) {
    className = "status failed";
  }

  return <span className={className}>{status}</span>;
}

function MetricCard({ label, value, description }) {
  return (
    <article className="metric-card">
      <p>{label}</p>
      <h2>{value}</h2>
      {description && <small>{description}</small>}
    </article>
  );
}

function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [builds, setBuilds] = useState([]);
  const [infrastructure, setInfrastructure] = useState(null);
  const [infrastructureDecision, setInfrastructureDecision] =
    useState(null);
  const [latestDecision, setLatestDecision] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [graphResult, setGraphResult] = useState(null);
  const [selectedBuildId, setSelectedBuildId] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const buildCounts = useMemo(() => {
    const successful = builds.filter((build) => {
      const status = getBuildStatus(build).toLowerCase();
      return status.includes("success") || status.includes("pass");
    }).length;

    const failed = builds.filter((build) => {
      const status = getBuildStatus(build).toLowerCase();
      return status.includes("fail") || status.includes("error");
    }).length;

    return {
      total: builds.length,
      successful,
      failed,
    };
  }, [builds]);

  async function loadDashboardData() {
    setLoading(true);
    setErrorMessage("");

    const results = await Promise.allSettled([
      getBuilds(),
      getInfrastructureSummary(),
      getInfrastructureDecision(),
      getDecisionRecords(),
    ]);

    const [
      buildsResult,
      infrastructureResult,
      infrastructureDecisionResult,
      decisionRecordsResult,
    ] = results;

    if (buildsResult.status === "fulfilled") {
      setBuilds(buildsResult.value);
    }

    if (infrastructureResult.status === "fulfilled") {
      setInfrastructure(infrastructureResult.value);
    }

    if (infrastructureDecisionResult.status === "fulfilled") {
      setInfrastructureDecision(infrastructureDecisionResult.value);
    }

    if (decisionRecordsResult.status === "fulfilled") {
      setLatestDecision(
        decisionRecordsResult.value?.decisions?.[0] ?? null
      );
    } else {
      setLatestDecision(null);
    }

    const failedRequests = results.filter(
      (result) => result.status === "rejected"
    );

    if (failedRequests.length > 0) {
      setErrorMessage(
        "Some dashboard data could not be loaded. Confirm that FastAPI and the local monitoring services are running."
      );
    }

    setLoading(false);
  }

  useEffect(() => {
    loadDashboardData();
  }, []);

  async function analyzeSelectedFailedBuild() {
    if (!selectedBuildId) {
      setErrorMessage("Select a failed build before requesting analysis.");
      return;
    }

    setAnalysisLoading(true);
    setErrorMessage("");

    try {
      const result = await analyzeFailedBuild(selectedBuildId);
      setGraphResult(result);
    } catch {
      setGraphResult(null);
      setErrorMessage(
        "Could not analyze the selected build. Confirm FastAPI is running and the selected build failed."
      );
    } finally {
      setAnalysisLoading(false);
    }
  }

  function renderOverview() {
    const probability =
      latestDecision?.failure_probability_percent;

    const isHighRisk =
      latestDecision && Number(probability) >= 70;

    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Dashboard</p>
            <h1>Overview</h1>
            <p>
              Safe local view of pipeline, deployment, and
              infrastructure health.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboardData}
          >
            Refresh data
          </button>
        </section>

        <section className="panel">
          <h2>Predicted Failure Risk</h2>

          <p className="prediction-value">
            {latestDecision
              ? `${Number(probability).toFixed(1)}%`
              : "Unavailable"}
          </p>

          <p>
            {isHighRisk
              ? "High risk — human review recommended"
              : latestDecision
                ? "Normal risk — normal human review process"
                : "No local prediction is available yet."}
          </p>
        </section>

        <section className="metric-grid">
          <MetricCard
            label="Total Pipelines"
            value={buildCounts.total}
          />
          <MetricCard
            label="Successful"
            value={buildCounts.successful}
          />
          <MetricCard
            label="Failed"
            value={buildCounts.failed}
          />
          <MetricCard
            label="Active Deployments"
            value={valueOrUnavailable(
              infrastructure?.running_pods
            )}
          />
          <MetricCard
            label="AI Fixes"
            value="0"
            description="Human approval required"
          />
          <MetricCard
            label="Rollbacks"
            value="0"
            description="Manual rollback only"
          />
        </section>

        <section className="panel">
          <h2>Infrastructure Snapshot</h2>

          <div className="metric-grid compact-grid">
            <MetricCard
              label="CPU"
              value={percentOrUnavailable(
                infrastructure?.cpu_percent
              )}
            />
            <MetricCard
              label="Memory"
              value={percentOrUnavailable(
                infrastructure?.memory_percent
              )}
            />
            <MetricCard
              label="Pod Restarts"
              value={valueOrUnavailable(
                infrastructure?.pod_restarts
              )}
            />
            <MetricCard
              label="HTTP Error Rate"
              value={percentOrUnavailable(
                infrastructure?.error_rate_percent
              )}
            />
          </div>
        </section>
      </>
    );
  }

  function renderPipelines() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Delivery</p>
            <h1>Pipelines</h1>
            <p>
              Pipeline information retrieved from your FastAPI API.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboardData}
          >
            Refresh data
          </button>
        </section>

        <section className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>Pipeline</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Branch</th>
                <th>Commit</th>
              </tr>
            </thead>

            <tbody>
              {builds.length === 0 ? (
                <tr>
                  <td colSpan="5">
                    No pipeline records are available yet.
                  </td>
                </tr>
              ) : (
                builds.map((build, index) => (
                  <tr key={build.id || build.build_id || index}>
                    <td>
                      {build.definition_name ||
                        build.pipeline ||
                        build.id ||
                        "Pipeline"}
                    </td>
                    <td>
                      <StatusBadge value={getBuildStatus(build)} />
                    </td>
                    <td>{build.duration || "Unavailable"}</td>
                    <td>
                      {build.source_branch ||
                        build.branch ||
                        "Unavailable"}
                    </td>
                    <td>
                      {build.source_version ||
                        build.commit ||
                        "Unavailable"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      </>
    );
  }

  function renderFailureDetails() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Investigation</p>
            <h1>Failure Details</h1>
            <p>
              Request concise, reviewable evidence only for a
              completed failed build.
            </p>
          </div>
        </section>

        <section className="panel">
          <h2>Analyze a Failed Build</h2>

          <p>
            This produces redacted, read-only evidence. It does not
            change code, Azure, Kubernetes, or infrastructure.
          </p>

          <select
            value={selectedBuildId}
            onChange={(event) => {
              setSelectedBuildId(event.target.value);
              setGraphResult(null);
            }}
          >
            <option value="">Select a failed build</option>

            {builds
              .filter((build) => {
                const status = getBuildStatus(build).toLowerCase();
                return (
                  status.includes("fail") ||
                  status.includes("error")
                );
              })
              .map((build) => {
                const buildId =
                  build.build_id || build.id || build.buildId;

                return (
                  <option key={buildId} value={buildId}>
                    Build #{buildId} —{" "}
                    {build.pipeline_name ||
                      build.definition_name ||
                      "Pipeline"}
                  </option>
                );
              })}
          </select>

          <button
            className="refresh-button"
            onClick={analyzeSelectedFailedBuild}
            disabled={!selectedBuildId || analysisLoading}
          >
            {analysisLoading
              ? "Analyzing…"
              : "Create Reviewable Analysis"}
          </button>
        </section>

        <section className="panel detail-grid">
          <div>
            <h3>Evidence Status</h3>
            <p>
              {graphResult
                ? "Reviewable evidence is available."
                : "No failed build has been analyzed yet."}
            </p>
          </div>

          <div>
            <h3>Log Handling</h3>
            <p>
              Only redacted, concise evidence may be reviewed. Raw
              private logs are not displayed.
            </p>
          </div>

          <div>
            <h3>Human Review</h3>
            <p>
              A human must inspect evidence before proposing or
              applying any change.
            </p>
          </div>
        </section>

        {graphResult?.fix_proposal?.explanation && (
          <section className="panel">
            <h2>Proposed Change</h2>

            <p>{graphResult.fix_proposal.explanation}</p>

            <p>
              <strong>Status:</strong>{" "}
              {graphResult.decision_status ===
              "awaiting_pr_approval"
                ? "Awaiting PR approval"
                : "Evidence ready"}
            </p>

            <p>
              Human inspection and explicit approval are required
              before any branch or pull-request action.
            </p>
          </section>
        )}
      </>
    );
  }

  function renderAIDecision() {
    const features = latestDecision?.features_used;

    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Reviewable AI output</p>
            <h1>AI Decision</h1>
            <p>
              This page displays only safe, concise decision data for
              human review.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboardData}
          >
            Refresh data
          </button>
        </section>

        <section className="panel detail-grid">
          <div>
            <h3>Prediction Probability</h3>
            <p>
              {latestDecision
                ? `${Number(
                    latestDecision.failure_probability_percent
                  ).toFixed(1)}%`
                : "Unavailable"}
            </p>
          </div>

          <div>
            <h3>Risk Level</h3>
            <p>{latestDecision?.risk_level ?? "Unavailable"}</p>
          </div>

          <div>
            <h3>Decision Status</h3>
            <p>
              {displayDecisionStatus(
                latestDecision?.decision_status
              )}
            </p>
          </div>

          <div className="wide-detail">
            <h3>Features Used</h3>
            <ul>
              <li>
                Files changed:{" "}
                {features?.files_changed ?? "Unavailable"}
              </li>
              <li>
                Changes count:{" "}
                {features?.changes_count ?? "Unavailable"}
              </li>
              <li>
                Previous failures in last 10 builds:{" "}
                {features?.previous_failures_10 ?? "Unavailable"}
              </li>
              <li>
                Dependency changes:{" "}
                {features?.dependency_changes ?? "Unavailable"}
              </li>
              <li>
                Previous deployment failures in last 10:{" "}
                {features?.previous_deployment_failures_10 ??
                  "Unavailable"}
              </li>
            </ul>
          </div>

          <div className="wide-detail">
            <h3>Concise Summary</h3>
            <p>
              {latestDecision?.summary ??
                "No reviewable decision summary is available yet."}
            </p>
          </div>

          <div className="wide-detail">
            <h3>Recommended Human Action</h3>
            <p>
              {latestDecision?.recommended_human_action ??
                "Create a local prediction before requesting human review."}
            </p>
          </div>
        </section>
      </>
    );
  }

  function renderPullRequests() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Code Review</p>
            <h1>Pull Requests</h1>
            <p>
              AI may recommend a fix, but a human must approve any
              pull request.
            </p>
          </div>
        </section>

        <section className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>PR</th>
                <th>Problem</th>
                <th>AI Fix</th>
                <th>Status</th>
                <th>Tests</th>
              </tr>
            </thead>

            <tbody>
              <tr>
                <td colSpan="5">
                  No pull-request data is connected yet. This is
                  expected until you add a read-only pull-request API
                  endpoint.
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </>
    );
  }

  function renderDeployments() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Kubernetes</p>
            <h1>Deployments</h1>
            <p>
              Deployment and rollback actions remain manual and
              human-approved.
            </p>
          </div>
        </section>

        <section className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Environment</th>
                <th>Status</th>
                <th>Health</th>
                <th>Rollback</th>
              </tr>
            </thead>

            <tbody>
              <tr>
                <td>Current local image</td>
                <td>staging</td>
                <td>
                  <StatusBadge
                    value={
                      infrastructure?.running_pods > 0
                        ? "Running"
                        : "Unavailable"
                    }
                  />
                </td>
                <td>
                  {infrastructure?.running_pods > 0
                    ? "At least one pod is running"
                    : "No pod-health result available"}
                </td>
                <td>Manual only</td>
              </tr>
            </tbody>
          </table>
        </section>
      </>
    );
  }

  function renderInfrastructure() {
    return (
      <>
        <section className="page-heading">
          <div>
            <p className="eyebrow">Prometheus Metrics</p>
            <h1>Infrastructure</h1>
            <p>
              Metrics are read through FastAPI. React does not connect
              to Prometheus directly.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboardData}
          >
            Refresh data
          </button>
        </section>

        <section className="metric-grid">
          <MetricCard
            label="CPU"
            value={percentOrUnavailable(
              infrastructure?.cpu_percent
            )}
          />
          <MetricCard
            label="Memory"
            value={percentOrUnavailable(
              infrastructure?.memory_percent
            )}
          />
          <MetricCard
            label="Pod Restarts"
            value={valueOrUnavailable(
              infrastructure?.pod_restarts
            )}
          />
          <MetricCard
            label="HTTP Error Rate"
            value={percentOrUnavailable(
              infrastructure?.error_rate_percent
            )}
          />
          <MetricCard
            label="Running Pods"
            value={valueOrUnavailable(
              infrastructure?.running_pods
            )}
          />
          <MetricCard
            label="Nodes"
            value={valueOrUnavailable(infrastructure?.nodes)}
          />
          <MetricCard
            label="Services"
            value={valueOrUnavailable(infrastructure?.services)}
          />
          <MetricCard
            label="Firing Alerts"
            value={valueOrUnavailable(
              infrastructure?.alerts_firing
            )}
          />
        </section>

        <section className="panel">
          <h2>Collection Status</h2>
          <p>
            Data collected at:{" "}
            {infrastructure?.collected_at
              ? new Date(
                  infrastructure.collected_at
                ).toLocaleString()
              : "Unavailable"}
          </p>
        </section>
      </>
    );
  }

  function renderPage() {
    if (activePage === "Overview") {
      return renderOverview();
    }

    if (activePage === "Pipelines") {
      return renderPipelines();
    }

    if (activePage === "Failure Details") {
      return renderFailureDetails();
    }

    if (activePage === "AI Decision") {
      return renderAIDecision();
    }

    if (activePage === "Pull Requests") {
      return renderPullRequests();
    }

    if (activePage === "Deployments") {
      return renderDeployments();
    }

    return renderInfrastructure();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">◆</span>

          <div>
            <p className="brand-label">LOCAL STAGING</p>
            <h2>Autonomous AI DevOps Engineer</h2>
          </div>
        </div>

        <nav>
          {pages.map((page) => (
            <button
              key={page}
              className={
                activePage === page
                  ? "nav-link active"
                  : "nav-link"
              }
              onClick={() => setActivePage(page)}
            >
              {page}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p>Safety mode enabled</p>
          <small>
            Human approval is required for fixes, PRs, deploys,
            rollbacks, and Terraform.
          </small>
        </div>
      </aside>

      <main className="main-content">
        {loading && (
          <div className="notice">Loading dashboard data…</div>
        )}

        {errorMessage && (
          <div className="notice warning">{errorMessage}</div>
        )}

        {renderPage()}
      </main>
    </div>
  );
}

export default App;