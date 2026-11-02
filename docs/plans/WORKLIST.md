# Automated Research System Worklist

Scope authority: [Accepted decisions](../status/DECISIONS.md).
Design: [Bounded AAR v1](../superpowers/specs/2026-11-02-bounded-aar-design.md).
Research reference: [Task specification v2.2](../IEEE118_OOD_Sample_Expansion_Task_v2_2.md).

This ledger replaces the initialization WP1–WP7 breakdown after the user confirmed the system-first foundation and bounded initial task.
Exactly one package is active. Status records evidence, not elapsed time.

| ID | Outcome and scope | Status | Dependencies | Acceptance |
|---|---|---|---|---|
| P0 | Research contract, upstream code mapping and initial system design. | complete | none | Accepted D001/D002; written design with observed source anchors, data boundaries and acceptance steps. |
| P1 | Reproducible real numerical trials and evidence. Pin AAR source and numerical environment; implement case/config provenance, validation, trial manifests and idempotent execution. | active | P0 | One real IEEE-118 baseline trial, independent residual validation, retained failure evidence, replay from frozen inputs, tests for duplicate requests and interrupted publication. |
| P2 | AAR single-researcher loop. Adapt domain prompt/tools, findings and snapshots; enforce external stopping and recovery. | pending | P1 | Real research session calls numerical tools, submits evidence-linked findings, survives interruption without losing completed trial identities or budget. |
| P3 | Independent verification and system acceptance. Isolate evaluation and replay evidence in a clean execution environment. | pending | P2 | Separate replay report, failed validation cases, process-recovery checks and one complete research trajectory. A supported negative result is acceptable. |
| P4 | First scientific deliverable: OOD sampling research. Freeze evaluation contract; compare strategies and replicate on held-out families. | pending | P3 | Equal-budget comparisons, separate equation/operational validity, defined coverage proxies, reproducible methods and independent evidence; report null results honestly. |

## Current evidence

- P0: `docs/status/DECISIONS.md` and the linked design.
- P1: environment discovery only, in `docs/status/BOOTSTRAP-PREFLIGHT.md`; the report's WP1 name refers to the previous ledger.
- No real power-flow trial, AAR runtime test or scientific improvement has been demonstrated.

## Execution constraints

- Preserve the user's bounded-autonomy model. Research workflow is autonomous; scope and evaluation remain governed.
- Preserve AAR collaboration capabilities while separating W2S dependencies. Ignored local changes alone are not reproducible integration.
- Freeze scenario and operating semantics before formal comparisons; baseline calibration is recorded separately.
- Distinguish research runs, numerical trials and execution attempts. Retries retain prior evidence and consume budget.
- A solver failure is unresolved, not proof of physical infeasibility.
- Never treat author-supplied scores as independently verified results.
- Real-case materials and downstream requirements remain open. Public prototype results do not establish business benefit.
