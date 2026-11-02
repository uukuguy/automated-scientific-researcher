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
| P2 | AAR single-researcher loop. Apply user-controlled variable contracts to domain prompt/tools, findings and snapshots; enforce external stopping and recovery. | complete | P1 | Real research session calls numerical tools, submits evidence-linked findings, survives interruption without losing completed trial identities or budget. |
| P3 | Independent verification and system acceptance, including D016 hypothesis lineage, scientific outcome semantics and model/compute ledgers. Isolate evaluation and replay frozen evidence. | active | P2 | Separate replay report, failed validation cases, process-recovery checks and one complete research trajectory. A supported negative result is acceptable; A12–A14 verify hypothesis history, outcome separation and resource accounting. |
| P4 | First scientific deliverable: sample-generation, solver-method or joint research. Freeze evaluation contract; compare candidates and replicate on held-out families. | pending | P3 | Equal-budget comparisons, separate equation/operational validity, defined coverage proxies, reproducible methods and independent evidence; report null results honestly. |

## Design and parallel preparation

The accepted architecture is detailed in [Minimum-loop design](../architecture/ASR-MINIMUM-LOOP.md). Its reference-profile control/admission, budget reservations, immutable publication and fenced recovery mechanisms have P1/P2 evidence; general candidate execution and P3 scientific-trust additions remain unimplemented. Acceptance IDs A1–A14 map to P1–P4. Capstone owns its separate C0–C4 preparation lane; no Capstone completion is inferred here.

## Current evidence

- P2 implemented: authenticated local control API, complete pinned-reference contract validation, immutable revisions, atomic trial/budget/dispatch, commands, candidate findings, fenced numerical execution and conservative recovery.
- P2 real subscription evidence: pi/Codex default gpt-6.1-sol/high produced one actual numerical trial and evidence-linked candidate finding; native-session reopen retained trial identity. See `docs/validation/P2-SUBSCRIPTION.md` and sanitized results. Clean reopen is not crash recovery.
- P2 accepted (bounded reference profile): actual pinned AAR loop/Experiment/Finding ORM, pi1.5 subscription trajectory05 with snapshot and candidate finding; process interruption/reopen04 retains native session and numerical IDs. Curated pack hashes, external stopping and source-integrity checks are enforced. Combined suite109 tests and scientific environment5 tests pass; evidence manifests independently checked. Tool-only calibration does not prove arbitrary candidate coding isolation.
- P3 active: independent evaluation environment and frozen replay report, negative validation cases and system trajectory acceptance. D016 accepts hypothesis revisions, outcome separation and separate logical model/compute ledgers (main design §§6.1,8,9). Implement and verify these within P3; do not rewrite historical P2 acceptance.
- Runtime direction accepted: subscription-first replaceable coding agents, pi baseline. GPT/Grok available; Claude pending. Other runtime subscription support is verified before activation.

- P0: `docs/status/DECISIONS.md` and the linked design.
- P1: `docs/validation/P1-NUMERICAL-LAB.md` and `P1-REFERENCE-RESULTS.json`; 28 focused tests, real baseline/replay/truncated/timeout trials. Original preflight is historical discovery evidence.
- Implementation slice: `docs/superpowers/plans/2026-11-02-container-lab.md`. The planned local reference slice is implemented and verified. Runtime database admission/budgets are implemented for the reference profile; generalized candidate service remains P2/P3 work.
- Real reference power-flow trials have been demonstrated. A pi subscription-backed calibration trajectory is verified; the pinned upstream AAR loop/ORM is demonstrated in trajectory05; scientific improvement has not been demonstrated. Paid API research requires separate explicit authorization.

## Execution constraints

- Human intervention follows main design §9.1 (accepted basic model). Capstone scientific-research architecture is accepted in §9.2/D009. Its parallel preparation follows `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`; protocol details remain to be aligned. Capstone owns C0–C4 in its ledger; P2 bounded single-researcher acceptance is complete; P3 is this repository’s active package.
- Solver methods and sampling are research variables from the start. Variable defaults and permitted changes come from the user-controlled contract.
- Preserve the user's bounded-autonomy model. Research workflow is autonomous; scope and evaluation remain governed.
- Preserve AAR collaboration capabilities while separating W2S dependencies. Ignored local changes alone are not reproducible integration.
- Freeze scenario and operating semantics before formal comparisons; baseline calibration is recorded separately.
- Distinguish research runs, numerical trials and execution attempts. Retries retain prior evidence and consume budget.
- A solver failure is unresolved, not proof of physical infeasibility.
- Never treat author-supplied scores as independently verified results.
- Real-case materials and downstream requirements remain open. Public prototype results do not establish business benefit.

## P3 implementation order under D016

1. Hypothesis revision and evidence relations: first local slice implemented with immutable revisions, optional frozen trial bindings, project checks, legacy replay, candidate author assessments and pi/AAR sharing. Interface tests exercise service reopen and opposing-evidence retention (A12); actual model-driven hypothesis revision and full trajectory remain outstanding.
2. Orthogonal outcome and Validation lifecycle: record execution separately from experiment validity and claim assessment; restrict official validation writes to evaluator identity (A13).
3. Two logical resource ledgers: preserve existing consumption through migration, atomically reserve model/compute dimensions, record unknown quota without silent fallback and test failure/recovery accounting (A14).
4. Minimal isolated candidate execution and evaluator replay: enable one contract-permitted candidate-method slice with real code/input/resource isolation, then prove execution/data/logic independence with real frozen-material replay and deliberate invalid cases (A8/A9). Integrate a complete negative-or-positive research trajectory; mocks alone cannot close P3.

## Risk checks during P3

- Highest: scientific trust. Inspect failure denominators, original-problem preservation, evaluator independence, exposed evaluation data and claim scope. Do not promote a metric improvement into a scientific finding.
- High: AAR coupling. Audit active prompt/tools/loop overrides and tracked patch size; keep upstream W2S/PGR task goals out of ASR contracts.
- High: infrastructure replacing research. Every P3 slice must serve the single-researcher hypothesis → candidate method → experiment → revision → finding → independent replay trajectory. Current reference-only iteration experiments do not prove candidate-method autonomy. No speculative multi-agent/distributed/plugin-platform work.
