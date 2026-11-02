---
name: code-review
description: Review a defined code change or technical review feedback for concrete correctness, research-integrity and regression risks.
---

# Code review

Establish the reviewed files or revision, intended behavior and relevant acceptance
criteria. Read the changed code with its callers, authoritative contracts and
existing checks. Scale the review to the change; prefer demonstrable failures over
style preferences or hypothetical redesigns.

Prioritize incorrect behavior, missing boundaries and regressions. In ASR, inspect
identity and revision handling, concurrent/replayed requests, execution ownership,
budget accounting, immutable evidence, and distinctions between author claims and
independent reports where the change touches them. Trace hypothesis/trial/evidence
references rather than trusting a label. Candidate code must not gain evaluator
permissions through a convenience path.

For each finding, provide a file/location, concrete trigger, consequence, supporting
reasoning and a focused remedy. State severity according to the consequence.
Separate confirmed defects from questions needing verification. If no actionable
issues are found, say so and identify only material untested behavior; do not invent
issues to fill a quota. Keep scientific disagreement separate from implementation
bugs.

When receiving feedback, verify the claim against actual code, requirements and
reproductions before applying it. Accept supported corrections and explain a
technical disagreement with evidence. Apply fixes when the current task authorizes
changes, then check the affected behavior. This method neither requires another
agent nor authorizes additional model calls, tools or changes.

Adapted from Superpowers review-request and review-reception guidance; source pins,
original hashes and MIT notice are in [the shared provenance catalog](../provenance.json).
