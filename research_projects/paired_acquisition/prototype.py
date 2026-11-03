"""UNTESTED design prototype: static block allocation and provenance contracts.

Not run, not a solver, trainer, independent validator or active-learning system.
Hashes bind supplied bytes/JSON; they do NOT authenticate scientific truth.
Trusted adapters must verify actual files, physics and fit execution externally.
"""
import copy
import hashlib
import json
import math

ARMS = {"TT": ("T0", "TA", "TB"), "BT": ("T0", "B", "TB"),
        "TG": ("T0", "TA", "G"), "BG": ("T0", "B", "G")}
CONTRACT_FIELDS = {"case_sha256", "original_sha256", "scenario_source_sha256",
                   "feature_source_sha256", "fit_source_sha256", "fit_policy_sha256",
                   "validator_source_sha256", "solver_source_sha256", "mask_sha256",
                   "protocol_sha256", "environment_sha256"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def point(x):
    require(isinstance(x, (list, tuple)) and len(x) == 3, "three coordinates")
    require(all(type(v) in (float, int) and math.isfinite(v) and .7 <= v <= 1.6
                for v in x), "finite coordinates in domain")
    return tuple(float(v) for v in x)


def static_plan(blocks, seed, excluded=()):
    """Input blocks are already generated/frozen by the protocol adapter.

    excluded contains original/evaluation/diagnostic and earlier-seed points.
    Cross-arm common blocks are intentional; no collision resampling occurs.
    """
    require(type(seed) is int and 1101 <= seed <= 1108, "locked seed set")
    require(set(blocks) == {"T0", "TA", "TB", "B", "G"}, "named blocks")
    seen = {point(x) for x in excluded}
    normalized = {}
    for name in ("T0", "TA", "TB", "B", "G"):
        require(len(blocks[name]) == (32 if name == "T0" else 16), "block size")
        normalized[name] = []
        for x in blocks[name]:
            key = point(x)
            require(key not in seen, "coordinate collision: abort manifest")
            seen.add(key)
            normalized[name].append(list(key))
    plan = []
    for arm, names in ARMS.items():
        for name in names:
            for i, x in enumerate(normalized[name]):
                plan.append(dict(proposal_id=f"{seed}/{arm}/{name}/{i}",
                                 seed=seed, arm=arm, stream=name, x=x))
    return dict(kind="static-plan/1", blocks_sha256=digest(normalized), rows=plan)


def check_contract(contract):
    require(set(contract) == CONTRACT_FIELDS, "complete fixed contract required")
    require(all(sha(v) for v in contract.values()), "contract digests")


def ingest(plan, receipts, contract, expected_inputs):
    """One terminal receipt per proposal; no silent retries/replacements.

    Checks are trusted-adapter statements, not independently recomputed here.
    expected_inputs maps every proposal ID to the exact scenario hash computed
    by a trusted adapter from fixed case/x, BEFORE solving, for ALL statuses.
    It must come from authenticated external provenance, not the solve receipt.
    Operational status is preserved but never used as a training filter.
    """
    plan, receipts = copy.deepcopy(plan), copy.deepcopy(receipts)
    expected_inputs = copy.deepcopy(expected_inputs)
    check_contract(contract)
    require(plan.get("kind") == "static-plan/1", "plan schema")
    proposals = {p["proposal_id"]: p for p in plan["rows"]}
    require(len(proposals) == len(plan["rows"]), "duplicate proposal IDs")
    by_id = {r["proposal_id"]: r for r in receipts}
    require(len(by_id) == len(receipts) and set(by_id) == set(proposals),
            "exactly one terminal receipt per slot, including failures")
    require(set(expected_inputs) == set(proposals)
            and all(sha(v) for v in expected_inputs.values()), "all attempted inputs bound")
    checked = []
    for pid, proposal in proposals.items():
        r = by_id[pid]
        require(r["proposal_sha256"] == digest(proposal), "proposal binding")
        require(r["contract_sha256"] == digest(contract), "contract binding")
        require(type(r["attempt_count"]) is int and r["attempt_count"] == 1,
                "one exact integer attempt; retries not authorized")
        require(type(r["elapsed_ms"]) is int and r["elapsed_ms"] >= 0, "cost")
        require(r["input_sha256"] == digest(r["input"])
                and r["input_sha256"] == expected_inputs[pid], "exact attempted input")
        check = r.get("check")
        if check is not None:
            require(check["input_sha256"] == r["input_sha256"]
                    and check["validator_source_sha256"] == contract["validator_source_sha256"],
                    "available checker provenance, regardless of label status")
            for field in ("input_preserved", "scenario_matches_proposal", "target_matches_solution"):
                if field in check:
                    require(check[field] is True, "integrity contradiction: stop all statuses")
            for field in ("solution_sha256", "y_sha256"):
                if field in check:
                    require(check[field] == r.get(field), "available checker binding")
        require(type(r["converged"]) is bool or r["converged"] is None,
                "separate convergence claim")
        require(r["status"] in ("labelled", "invalid_label", "label_failure"),
                "terminal label status")
        if r["status"] == "labelled":
            require(r["solution_sha256"] == digest(r["solution"]), "solution hash")
            require(r["y_sha256"] == digest(r["y"]), "target hash")
            require(len(r["y"]) == 236 and all(type(v) in (int, float)
                    and math.isfinite(v) for v in r["y"]), "canonical target shape")
            check = r["check"]
            require(check["input_sha256"] == r["input_sha256"]
                    and check["solution_sha256"] == r["solution_sha256"]
                    and check["y_sha256"] == r["y_sha256"], "checker binding")
            require(check["validator_source_sha256"] == contract["validator_source_sha256"],
                    "checker source")
            require(check["equation_valid"] is True and check["input_preserved"] is True
                    and check["target_matches_solution"] is True
                    and check["scenario_matches_proposal"] is True,
                    "integrity contradiction: block run, do not silently drop row")
            require(check["tolerance_pu"] == 1e-7, "fixed equation tolerance")
            require(check["operational_status"] in ("violated", "satisfied", "unassessed"),
                    "separate operating assessment")
            require(type(check["thermal_limits_unassessed"]) is int
                    and check["thermal_limits_unassessed"] >= 0, "missing limits")
        else:
            require(r.get("y") is None, "failed slot has no training target")
            if r["status"] == "label_failure":
                require(bool(r.get("error")), "preserve genuine solve exception")
            else:
                require(check is not None and check["equation_valid"] is False
                        and bool(r.get("reason")), "preserve equation-invalid check/reason")
        checked.append(dict(proposal=proposal, receipt=r, receipt_sha256=digest(r)))
    return dict(kind="checked-ledger/1", plan=plan, expected_inputs=expected_inputs,
                plan_sha256=digest(plan),
                contract_sha256=digest(contract), records=checked,
                proposed=len(checked), elapsed_ms=sum(r["elapsed_ms"] for r in receipts))


def training_manifest(ledger, arm, seed, original_rows, contract, expected_ledger_sha256):
    """External immutable-store pin is mandatory; never derive it from this input."""
    ledger, original_rows = copy.deepcopy(ledger), copy.deepcopy(original_rows)
    check_contract(contract)
    require(sha(expected_ledger_sha256) and digest(ledger) == expected_ledger_sha256,
            "immutable ledger pin")
    require(ledger["plan_sha256"] == digest(ledger["plan"]), "saved plan hash")
    for v in ledger["records"]:
        require(v["receipt_sha256"] == digest(v["receipt"])
                and v["receipt"]["proposal_sha256"] == digest(v["proposal"]),
                "saved receipt/proposal hashes")
    rebuilt = ingest(ledger["plan"], [v["receipt"] for v in ledger["records"]],
                     contract, ledger["expected_inputs"])
    require(digest(rebuilt) == digest(ledger), "revalidate ledger before assembly")
    require(ledger["contract_sha256"] == digest(contract), "ledger contract")
    require(len(original_rows) == 128 and digest(original_rows) == contract["original_sha256"],
            "unaltered original128")
    records = [v for v in ledger["records"] if v["proposal"]["arm"] == arm
               and v["proposal"]["seed"] == seed]
    require(len(records) == 64, "complete arm, failures included")
    rows = list(original_rows)
    for v in records:
        p, r = v["proposal"], v["receipt"]
        if r["status"] == "labelled":
            rows.append(dict(sample_id=p["proposal_id"], x=p["x"], y=r["y"]))
    return dict(kind="training-manifest/1", arm=arm, seed=seed, rows=rows,
                ledger_sha256=digest(ledger), contract_sha256=digest(contract),
                training_sha256=digest(rows), proposed=64, labelled=len(rows)-128)


def bind_model(manifest, model_receipt, expected_manifest_sha256):
    """External trusted fit receipt and immutable-store pin are mandatory."""
    manifest, model_receipt = copy.deepcopy(manifest), copy.deepcopy(model_receipt)
    require(sha(expected_manifest_sha256) and digest(manifest) == expected_manifest_sha256,
            "immutable manifest pin")
    require(digest(manifest["rows"]) == manifest["training_sha256"], "recompute training hash")
    require(model_receipt["training_sha256"] == manifest["training_sha256"], "training binding")
    require(model_receipt["contract_sha256"] == manifest["contract_sha256"], "fit binding")
    require(model_receipt["model_sha256"] == digest(model_receipt["model"]), "model hash")
    return dict(manifest_sha256=digest(manifest), receipt_sha256=digest(model_receipt))


def memory_entry(previous_entry_sha256, artifact, source_snapshot_sha256, claim):
    """Append-only candidate record; no independent-validation verdict field."""
    require(previous_entry_sha256 is None or sha(previous_entry_sha256), "previous hash")
    require(sha(source_snapshot_sha256), "source snapshot")
    entry = dict(kind="candidate-memory/1", previous=previous_entry_sha256,
                 artifact_sha256=digest(artifact), source_snapshot=source_snapshot_sha256,
                 claim=claim, evidence_status="author-supplied-unvalidated")
    return dict(entry=entry, entry_sha256=digest(entry))
