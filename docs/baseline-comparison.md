# Traditional DevOps vs AI DevOps Engineer — Baseline Comparison

## Purpose

This comparison evaluates whether AI-assisted, human-controlled analysis improves workflow timing and quality compared with a traditional manual DevOps workflow.

All measured incidents must be classified as `test` or `real`. Fake local scenarios classified as `demo` are excluded from research metrics.

## Fair Comparison Rules

- Use comparable non-production failures or genuine incidents.
- Record all timestamps in UTC.
- Use the same definition of each milestone for both workflows.
- Root cause is counted only after human confirmation.
- A repair is counted only after a human-approved change passes validation.
- AI output remains advisory; it must not create branches, pull requests, deployments, rollbacks, Terraform changes, or Kubernetes changes.
- Do not treat unavailable data as zero.

## Timestamp Definitions

| Milestone            | Definition                                              |
| -------------------- | ------------------------------------------------------- |
| Failure observed     | Azure build failure completion time                     |
| Failure detected     | Time the workflow records the failure for review        |
| Root cause confirmed | Time a human confirms the evidence-supported root cause |
| Repair verified      | Time a human confirms the repaired build or test passed |

## Per-Incident Records

| Incident key                  | Dataset          | Workflow         | Failure observed | Failure detected | Human-confirmed root cause | Repair verified | Fix succeeded | Notes             |
| ----------------------------- | ---------------- | ---------------- | ---------------- | ---------------- | -------------------------- | --------------- | ------------- | ----------------- |
| *Add approved incidents here* | `test` or `real` | Traditional / AI | UTC              | UTC              | UTC                        | UTC             | Yes / No      | Safe summary only |

## Comparison Metrics

| Metric                         |                         Traditional DevOps | AI System | Notes                                                                   |
| ------------------------------ | -----------------------------------------: | --------: | ----------------------------------------------------------------------- |
| Failure detection time         |                                    Pending |   Pending | `failure_detected_at − failure_observed_at`                             |
| Root-cause identification time |                                    Pending |   Pending | `root_cause_confirmed_at − failure_observed_at`                         |
| Repair time                    |                                    Pending |   Pending | `repair_verified_at − failure_observed_at`                              |
| Successful fixes               |                                    Pending |   Pending | Human-verified fixes only                                               |
| False predictions              | N/A unless manual predictions are recorded |   Pending | High-risk prediction followed by a successful build is a false positive |
| Rollbacks                      |                                    Pending |   Pending | Human/manual rollback only                                              |

## Current Status

- [x] Comparison methodology defined.
- [ ] Comparable approved `test` or `real` incidents collected.
- [ ] Traditional workflow measurements recorded.
- [ ] AI workflow measurements recorded.
- [ ] Human-confirmed root-cause results recorded.
- [ ] Human-tested repair results recorded.
- [ ] Evidence-based comparison calculated.

## Reporting Rule

No performance-improvement claim will be made until comparable, human-verified `test` or `real` measurements are available for both workflows.
