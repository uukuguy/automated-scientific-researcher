---
name: verification-before-completion
description: Match completion, correctness or scientific-result claims to current observable evidence before reporting them as established.
---

# Verification before completion

Identify the claim and the smallest sufficient observable check for the current
revision, configuration and artifact. Run that check with permitted tools, inspect
its complete outcome and explain what it establishes. A command starting, a prompt
being accepted, or an agent reporting success is not completion evidence.

Use focused behavioral checks for code changes and broaden verification when a
failure or unresolved risk warrants it. A defect fix should exercise its original
trigger. If evidence predates the relevant change, obtain current evidence before
claiming that change passes. Do not invoke unavailable execution tools or treat a
skill as permission to bypass the configured budget.

For research, distinguish execution exit, solver claims, independent equation
validity, operating limits, reproducibility and generalization. Numerical claims
need actual numerical evidence. Autonomous-research claims need an actual model
trajectory. Mock checks establish only the interface behavior they exercise.
A successful calibration run does not validate a new method or establish novelty.

Report the observed result, evidence reference and material limits together. State
failed, interrupted, unassessed and unexecuted checks accurately. Unknown live
processes remain unresolved; a local note cannot release their budget or establish
that they exited. Verification does not authorize rewriting published evidence or
self-issuing an evaluator verdict.

Adapted from Superpowers; source pin, original hash and MIT notice are recorded in
[the shared provenance catalog](../provenance.json).
