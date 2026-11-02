# Research variable policy

`variable-policy.schema.json` describes `asr-variable-policy/1`, a component of the future `asr-contract/1`. It is not the full executable contract. The example contains network, iteration and solver variables; it does not authorize a numerical or model run.

Run checks with `uv sync --locked` and `uv run python -m unittest discover -s tests -v`.

`asr_service.contracts.resolve_policy(template, overrides)` copies defaults into effective values, rejects undeclared fields/types/units, and checks bounds. User overrides can change value, mode, allowed range, modification roles and implementation description; changing declared types or units requires a new template. A default can lie outside a newly narrowed range only when an explicit effective value is valid. `check_change` checks a candidate value, role and scope without mutating policy. Fixed values require a new policy revision to change. Open values still need service-level capability and budget admission.

`PolicyStore(path)` owns only `asr_policy_*` tables. `publish` requires an expected revision (0 for creation), a project-scoped idempotency key and a resolved policy. Repeating the same request returns the original revision; changed content or stale expected revision is rejected. Publications and events commit in the same SQLite transaction. `get` returns a detached document.

`apply` explicitly switches a binding for an external run ID using the binding's control revision (0 for initial binding). Publication does not change that binding. It does not create a research run, validate a real upstream run, reserve budget or start a process. Apply currently uses compare-and-swap, not the future idempotent HTTP command envelope; callers must read the binding after uncertain responses. These local bindings will be incorporated into the owning runtime's transaction before real trial admission is added.

The actor argument is a trusted in-process role assertion, **not authentication**. Public callers must not directly invoke these methods or supply their own trusted actor. Project grants, registered problem/evaluation references, complete budgets, capability checks, migrations and HTTP envelopes remain P2 work. An empty database may be initialized for local tests; no AAR production database was modified.

The example is an editable template, not a newly imposed limit on all research. Capstone may consume the schema and examples to prepare forms; semantic checks remain authoritative on the server side. Do not advertise this sub-schema as the complete cross-project contract.
