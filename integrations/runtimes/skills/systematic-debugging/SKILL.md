---
name: systematic-debugging
description: Diagnose software failures or unexpected experiment behavior by tracing evidence to a testable root cause before changing code.
---

# Systematic debugging

Identify the failing boundary: admission, runtime, execution, solver claim,
independent equation checks, operating constraints, or evidence publication.
Nonconvergence and a negative scientific result are observations, not automatically
software defects. Record the actual error, input/configuration versions, environment
and run/trial/attempt IDs; preserve the original failed evidence.

Compare a minimal reproduction with a working case. Trace the unexpected value
back through the relevant boundaries and inspect recent changes. Diagnostics
should expose state and credential presence, never secret values. Distinguish a
reproducible defect from an intermittent effect that needs more observation.

State a specific causal hypothesis and the cheapest permitted check that would
distinguish it from alternatives. Change one relevant factor when practical.
Do not stack speculative fixes or silently change the scientific problem to make
an experiment pass. If an earlier execution may still be live, reconcile its
identity before retrying; failed costs remain consumed.

Apply a focused correction within the authorized workspace. Verify the original
symptom and affected behavior using available test or sandbox tools. If execution
is unavailable, report the untested hypothesis and proposed check. Repeated
unsuccessful fixes justify revisiting assumptions and coupling, not endless retries.
Never alter immutable evidence, hidden evaluation assets or independent evaluators
to repair candidate results.

Adapted from Superpowers; source pin, original hash and MIT notice are recorded in
[the shared provenance catalog](../provenance.json).
