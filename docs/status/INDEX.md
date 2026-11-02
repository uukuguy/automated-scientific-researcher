# docs/status INDEX

Catalog of repository state files.

Status legend: 🟢 active; 🟡 decision history; 🔴 superseded; ⚫ scratch.
Read active files on resume. Historical recommendations may no longer apply.
Register each new status file here. Register archive buckets as one row per bucket.

## Active

| File | Status | Purpose |
|---|---|---|
| `CURRENT-STATE.md` | 🟢 active | Structural snapshot. |
| `JOURNAL.md` | 🟢 active | Append-only event log. |
| `RESUME-NEXT-SESSION.md` | 🟢 active | Session recovery point. |
| `INDEX.md` | 🟢 active | File catalog. |
| `DECISIONS.md` | 🟢 active | Accepted scope, interaction, Capstone architecture and subscription-first replaceable runtimes and omp/AAR, power-grid capability base and locked scientific stack, and D016 scientific trust and D018 three-layer AAR/Capstone organization (superseding D017); protocol details remain draft. |
| `BOOTSTRAP-PREFLIGHT.md` | 🟡 decision history | Initial environment discovery; current numerical evidence is in docs/validation/P1-NUMERICAL-LAB.md. |

## Decision history

| File | Status | What it recorded | Outcome / supersession |
|---|---|---|---|

## Archived

| Bucket | Files | Notes |
|---|---|---|

## Knowledge routing

Technical invariants belong in CLAUDE.md; architectural choices belong in DECISIONS.md.
Collaboration preferences belong in MEMORY.md. Complete evidence stays in indexed topic files.

## External anchors

- `docs/plans/WORKLIST.md` — canonical packages and acceptance gates.
- `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md` — research objective and requirements.

- `docs/PROJECT-DESIGN.md` — canonical current design; read before implementation or design discussion.
- `docs/superpowers/plans/2026-11-02-container-lab.md` — current numerical-environment implementation slice.
- `docs/superpowers/specs/2026-11-02-bounded-aar-design.md` — historical redirect; not a separate design authority.

- `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md` — Capstone preparation tasks, proposed service contract and acceptance boundaries.

- `docs/architecture/ASR-MINIMUM-LOOP.md` — detailed minimum-loop design, interface candidate and acceptance mapping.

- `docs/validation/P1-NUMERICAL-LAB.md` and `P1-REFERENCE-RESULTS.json` — P1 local numerical acceptance and remaining boundaries.

- `docs/superpowers/plans/2026-11-02-contract-core.md` — P2 variable-policy slice and limits.
- `contracts/README.md` — implemented variable sub-schema and local API.

- `docs/architecture/RESEARCHER-RUNTIMES.md` — accepted subscription-first runtime boundary and provider verification states.

- `docs/validation/P2-SUBSCRIPTION.md` and `P2-SUBSCRIPTION-RESULTS.json`, `P2-INTERRUPTION-RESULTS.json`, `P2-AAR-RESULTS.json` — real subscription, interruption and actual upstream AAR trajectories with explicit acceptance limits.

- `docs/validation/SDK-PROTOTYPES.md` — Context7 and installed-version SDK interface verification.

- `docs/validation/PANDAPOWER-CALIBRATION.md` — locked scientific environment, IEEE118 cross-calibration and raw conversion differences.

- `docs/validation/TOOL-PACK.md` and `CONTEXT7-RESULTS.json` — shared skills, actual pi loading and bounded public documentation/literature connectivity.

- Native runtime implementation order and acceptance gates: `docs/architecture/RESEARCHER-RUNTIMES.md`, decisions D019–D020.
- `docs/architecture/RESEARCH-ORGANIZATION-REFERENCES.md` — bounded DeepSeek and shared native-runtime reference analysis.
- `docs/validation/NATIVE-RUNTIME-PROTOCOLS.md` — no-inference native protocol discovery and explicit remaining acceptance gates.
- `docs/validation/CODEX-APP-SERVER-CONVERSATION.json` and `GROK-ACP-CONVERSATION.json` — actual bounded native dialog success and retained timeout, respectively.
