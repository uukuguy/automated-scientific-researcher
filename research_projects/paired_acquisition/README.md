# Paired acquisition research deliverable

`prototype.py` is an exact, unmodified copy of the P5 Lead's final
`acquisition_ledger.py`, SHA256
`7587e7161c26863df3be96c3376331d44234b37c7da98e391a168aea179fe2fb`,
from snapshot `29c1fa7302d7ded1492ce5b7b9b17457f8ad3fe3401c7be2a3587b1354dac262`,
run `research_ea8d744abd5e4a31bc913d1564f12528`.
The original header accurately describes its state at delivery. Subsequent
engineering checks are recorded in `docs/validation/P5-PAIRED-ADAPTER.md`.
Do not silently edit this source or attribute controller changes to the Lead.

The prototype allocates already supplied blocks to four paired arms. It does
not generate OOD coordinates, learn a boundary, solve equations, or establish
training benefit. Its fixed block names and seed set belong to this particular
research proposal, not ASR's organization or general-purpose sampling policy.

`native_adapter.py` is controller-authored integration code. Before dispatch,
`prepare_inputs` reconstructs each input from a pinned case and the existing
regional load/dispatch rule. `convert` checks an authenticated native row against
that expected input, independently rebuilds the AC equations, and checks the
voltage/angle target order. It retains operating violations, unassessed thermal
limits, exception types, equation-invalid results and elapsed time.

The caller must verify Control dispatch, immutable evidence manifests, complete
slot coverage, and externally frozen contract/source/plan pins. These functions
are not an authentication service or an automatic experiment scheduler. The
adapter has not yet been wired into a model-driven team science run. Training
manifest and model receipt binding still need end-to-end verification with the
frozen original 128 training rows and the actual trainer. A one-row ingestion
check is not validation of a 3584-slot scientific comparison.
