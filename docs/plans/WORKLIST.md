# Automated Research System Worklist

Scope authority: [Accepted decisions](../status/DECISIONS.md).
Current design: [Project design](../PROJECT-DESIGN.md).
Research reference: [Task specification v2.2](../IEEE118_OOD_Sample_Expansion_Task_v2_2.md).

This ledger replaces the initialization WP1–WP7 breakdown after the user confirmed the system-first foundation and bounded initial task.
Exactly one package is active. Status records evidence, not elapsed time.

| ID | Outcome and scope | Status | Dependencies | Acceptance |
|---|---|---|---|---|
| P0 | Research contract, upstream code mapping and initial system design. | complete | none | Accepted D001–D006; written design with observed source anchors, data boundaries and acceptance steps. |
| P1 | Reproducible real numerical trials and evidence. Pin AAR source and numerical environment; implement case/config provenance, validation, trial manifests and idempotent execution. The reference solver is a baseline, not a candidate-method restriction. | complete | P0 | One real IEEE-118 baseline trial, independent residual validation, retained failure evidence, replay from frozen inputs, tests for duplicate requests and interrupted publication. |
| P2 | AAR single-researcher loop. Apply user-controlled variable contracts to domain prompt/tools, findings and snapshots; enforce external stopping and recovery. | active | P1 | Real research session calls numerical tools, submits evidence-linked findings, survives interruption without losing completed trial identities or budget. |
| P3 | Independent verification and system acceptance. Isolate evaluation and replay evidence in a clean execution environment. | pending | P2 | Separate replay report, failed validation cases, process-recovery checks and one complete research trajectory. A supported negative result is acceptable. |
| P4 | First scientific deliverable: sample-generation, solver-method or joint research. Freeze evaluation contract; compare candidates and replicate on held-out families. | pending | P3 | Equal-budget comparisons, separate equation/operational validity, defined coverage proxies, reproducible methods and independent evidence; report null results honestly. |

## Design and parallel preparation

The accepted architecture is detailed in [Minimum-loop design](../architecture/ASR-MINIMUM-LOOP.md). Its technical mechanisms are designed, not implemented: contract publication/application, independent control revisions, transactionally admitted trials, budget reservations, immutable publication, fenced recovery and the control API candidate. Acceptance IDs A1–A11 map to P1–P4. Capstone owns its separate C0–C4 preparation lane; no Capstone completion is inferred here.

## Current evidence

- P2 partial: variable-policy schema/defaults/semantics and local immutable revisions with explicit binding activation; 10 new tests (38 total). Full reference/budget admission, authentication, HTTP and AAR execution remain pending.

- P0: `docs/status/DECISIONS.md` and the linked design.
- P1: `docs/validation/P1-NUMERICAL-LAB.md` and `P1-REFERENCE-RESULTS.json`; 28 focused tests, real baseline/replay/truncated/timeout trials. Original preflight is historical discovery evidence.
- Implementation slice: `docs/superpowers/plans/2026-11-02-container-lab.md`. The planned local reference slice is implemented and verified. Runtime database admission/budgets and the generalized candidate service belong to P2/P3.
- Real reference power-flow trials have been demonstrated. No AAR runtime test or scientific improvement has been demonstrated. P2 starts with schema/control preparation; paid research requires an authorized configured budget.

## Execution constraints

- Human intervention follows main design §9.1 (accepted basic model). Capstone scientific-research architecture is accepted in §9.2/D009. Its parallel preparation follows `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`; protocol details remain to be aligned. Capstone owns C0–C4 in its ledger; P2 is now this repository’s active package after P1 reference acceptance.
- Solver methods and sampling are research variables from the start. Variable defaults and permitted changes come from the user-controlled contract.
- Preserve the user's bounded-autonomy model. Research workflow is autonomous; scope and evaluation remain governed.
- Preserve AAR collaboration capabilities while separating W2S dependencies. Ignored local changes alone are not reproducible integration.
- Freeze scenario and operating semantics before formal comparisons; baseline calibration is recorded separately.
- Distinguish research runs, numerical trials and execution attempts. Retries retain prior evidence and consume budget.
- A solver failure is unresolved, not proof of physical infeasibility.
- Never treat author-supplied scores as independently verified results.
- Real-case materials and downstream requirements remain open. Public prototype results do not establish business benefit.


### P2 local budget primitive (2026-11-02)

本地预算原语 `asr_service/budgets.py` 已实现项目级整数计量、事务预留、幂等结算及超额记账。执行退出由可信调用方声明，尚未连接进程核验、运行子额度、完整准入或 AAR；不能作为执行授权。

- P2 budget preparation: atomic multidimension reservations can join an owning transaction; 44 tests pass. Trial admission and AAR remain pending.

- P2 reference preparation: immutable project/kind-scoped JSON metadata registry with read-time hash verification; 47 combined tests pass. No external artifact or complete-contract admission claim.

- P2 local admission preparation: atomic policy/reference checks, trial identities, budget bundle and event; 50 combined tests pass. Owner gate remains an unintegrated trusted callback; no real admission API or dispatch.

- P2 recovery correction: authorized replay survives closed admission gates; unauthorized replay and new paused submissions are rejected. 51 combined tests pass.

- P2 runtime direction: user accepted subscription-first replaceable coding agents and pi lightweight baseline; actual subscription-backed scientific trajectory remains required.
