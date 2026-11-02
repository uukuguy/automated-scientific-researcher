# P2 Variable policy and revision core

Scope: implement the variable-policy part of the research contract, not the complete executable contract or HTTP API. Main design §5 and minimum-loop design §2 govern behavior.

- [x] JSON Schema and example: typed variables, fixed/bounded/open, units, scope, permissions and explicit open execution interface.
- [x] Pure validation: defaults, declared overrides, unknown field rejection, finite numbers, type/range/permission checks.
- [x] SQLite revision repository: immutable publication, idempotency, optimistic revision checks, explicit binding activation and same-transaction events.
- [x] Tests: invalid scope/value changes, conflicting requests, stale publication/activation, cross-project references, concurrent publication and persistent reopen.
- [x] Align main design, README, instructions, worklist and Capstone handoff. Publication of a variable policy does not authorize execution: problem/evaluation references, budgets and capabilities remain required at future admission.

Use trusted in-process repository methods for this slice. Database connection path is provided by the owner; tables have ASR prefixes for later integration with the AAR database. Binding records associate external run IDs with policy revisions; they do not create or schedule research runs. No model call, numerical experiment or Capstone write is required.

Verification: 10 focused contract tests and 38 combined tests passed. Full executable-contract admission and HTTP semantics remain outside this slice.
