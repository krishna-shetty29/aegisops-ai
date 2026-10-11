# Research Metrics

Date: 2026-10-09
Project: Autonomous AI DevOps Engineer
Data policy: Use only safe metadata, redacted evidence, and human-verified outcomes. Never record tokens, passwords, API keys, database URLs, raw private logs, or prompts.

## Metric Definitions

| Metric | Definition |
| --- | --- |
| MTTD | Time from an Azure build first being recorded as failed to a safe local failure-detection or analysis record being created. |
| MTTR | Time from an Azure build first being recorded as failed to a human-verified repair or test-success result. |
| Failure prediction accuracy | A prediction is correct when its high/normal result matches the final Azure build outcome. |
| AI root-cause accuracy | A root-cause result is correct only when a human reviewer confirms it is supported by the available evidence. |
| Fix success rate | A fix is successful only when a human-approved AI proposal is tested and passes. |
| Rollback success rate | A rollback is successful only when a human manually verifies that a non-production service recovered. |

## Prediction Rule

A prediction is treated as `predicted_failure = true` when:

- `risk_level` is `high`
- `failure_probability_percent` is 70 or greater

A prediction is treated as `predicted_failure = false` when:

- `risk_level` is `normal`
- `failure_probability_percent` is below 70

## Timestamp Rule

- `failure_observed_at`: Azure build failure completion time.
- `failure_detected_at`: time the safe local analysis or decision record is created.
- `repair_verified_at`: time a human confirms the repaired build or test passed.

## Research Data Rule

- `demo`: fake, redacted local scenarios.
- `test`: approved non-production tests.
- `real`: genuine incidents.

Demo results must never be mixed with test or real accuracy claims.

## Important Interpretation Rule

An AI proposal is not a successful repair.

Count a repair as successful only after:

1. A human approves the proposed fix.
2. The fix is tested.
3. A human verifies that the test or repaired build passed.

## Current Status

| Metric | Current result | Reason |
| --- | --- | --- |
| MTTD | Not available | No timestamped approved non-production incident recorded yet. |
| MTTR | Not available | No human-verified repair was performed. |
| Failure prediction accuracy | Not available | No labeled prediction/outcome dataset exists yet. |
| AI root-cause accuracy | Initial demo complete | Six fake scenarios were reviewed; real/test labels still required. |
| Fix success rate | Not available | No AI proposal was human-tested as a code fix. |
| Rollback success rate | Not available | No approved non-production rollback was attempted. |

## Safety Boundary

- AI output remains evidence-based and proposal-only.
- Humans control pull-request approval, deployment, rollback, Terraform, and Kubernetes actions.
- No API endpoint automatically creates a branch, creates a pull request, deploys, rolls back, or modifies infrastructure.

## Current Step 45 Status

- [x] Measurement framework completed.
- [x] Dataset separation defined: `demo`, `test`, and `real`.
- [x] One retrospective test failure has safe observed and detected timestamps.
- [ ] Prediction-accuracy measurements pending valid pre-build predictions.
- [ ] Human-confirmed root-cause measurements pending.
- [ ] Human-tested fix-success measurements pending.
- [ ] Manual rollback measurements pending.

**Status:** Step 45 measurement framework is complete. Empirical metrics remain pending future approved `test` or genuine `real` incidents.