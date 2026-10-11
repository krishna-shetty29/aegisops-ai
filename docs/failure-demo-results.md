# Deliberate Failure Demonstration Results

All scenarios used fake, redacted local logs only.

| Scenario | Detection | AI analysis | Human-reviewed proposed fix | Result |
| --- | --- | --- | --- | --- |
| Dependency failure | [x] | [x] | [x] | [x] Passed |
| Unit-test failure | [x] | [x] | [x] | [x] Passed |
| Docker build failure | [x] | [x] | [x] | [x] Passed |
| Invalid environment setting | [x] | [x] | [x] | [x] Passed |
| Kubernetes configuration problem | [x] | [x] | [x] | [x] Passed |
| Health-check failure | [x] | [x] | [x] | [x] Passed |

## Safety Confirmation

- [x] No real Azure logs, tokens, passwords, or production data were used.
- [x] No AI-created branch or pull request was used.
- [x] No automatic deployment or rollback occurred.
- [x] All fixes remained proposals requiring human approval.

## Manual PR Validation Demonstration

- [x] An existing human-created PR (#4) targeting `main` was used.
- [x] The PR remained under human control.
- [x] Azure DevOps ran the required `sample-app` PR validation.
- [x] The validation ran as a Pull request build and completed successfully.
- [x] No fake failure log created a real production fix PR.
- [x] No AI-created branch, pull request, deployment, or rollback was used.

### Azure Build Outcome

- Azure build ID: `42`
- Pipeline run: `20261008.2`
- Pipeline: `sample-app`
- Run reason: `pullRequest`
- Source branch: `refs/pull/4/merge`
- Status: `completed`
- Result: `succeeded`
- Queue time: `2026-10-08T16:25:36.6233058Z`
- Finish time: `2026-10-08T16:27:04.8009557Z`
- `actual_failure`: `false`
- Deployment: Not performed
- Rollback: Not performed
- Note: No local pre-build prediction was recorded for build `42`, so it is excluded from prediction-accuracy calculations.

## Final Safety Verification

| Area | Verified result |
| --- | --- |
| Local tests | [x] Pytest passed locally. |
| Parser and sanitizer | [x] Huge-log limits and secret redaction passed. |
| AI safety scenarios | [x] Six fake, redacted failure scenarios were analyzed safely. |
| PR validation | [x] Human-created PR #4 passed required Azure validation. |
| Deployment | [x] Not performed: no approved non-production deployment pipeline exists. |
| Rollback | [x] Not performed: no deployment failure occurred. |
| Human control | [x] Humans retain control over PR approval, deployment, and rollback. |
| Automation boundary | [x] No AI-created branch, PR, deployment, rollback, Terraform, or Kubernetes action occurred. |