# Shared research capability pack /3

Date: 2026-11-02. Source materials and runtime loading are implemented; this is
not an autonomous scientific discovery or full P3 acceptance report.

- Five skills: scientific-reasoning/2, systematic-debugging/1, code-review/1,
  verification-before-completion/1 and deep-research/1. The source catalog records
  exact upstream Superpowers revision, original hashes and MIT notice; ASR edits
  remove mandatory external delegation and workflow permissions.
- pi1.5's actual loadSkillsFromDir parsed all five with zero diagnostics. Four new
  skills also passed skill-creator validation. Per-session files are hash-checked,
  frozen read-only and explicitly passed to pi; ambient discovery remains disabled.
- Context7 public search and documentation calls succeeded without installing a
  credential. [Sanitized receipt](CONTEXT7-RESULTS.json) records the requested
  version as unverified by the provider. Documentation is checked against local
  installed signatures before implementation claims.
- Crossref public query `Newton Raphson power flow`, limit3, succeeded at
  2026-11-02T15:22:06Z. DOI metadata returned:10.32920/ryerson.14644656,
  10.32920/ryerson.14644656.v1 and10.1201/b19739-3. This is search connectivity,
  not a quality ranking or full-text review; versions/duplicates need appraisal.
- Final combined optional-AAR suite141 tests passed5.945s. Covers malformed input,
  response bounds, redirect rejection, provider errors, immutable skill sources,
  explicit file access and legacy-profile rejection. No new model calls.

Tool requests remain counted by the existing runtime tool permit ledger.
Context7 additionally caps calls per bridge instance. Clients have bounded socket
waits/read deadlines and response sizes, with no automatic retries; DNS is not a
hard total-time bound in urllib. A strict whole-operation deadline needs external
supervision. No arbitrary URL fetch, evaluation assets or candidate-container
network access is granted. The HTTP bridge is pi-facing; Claude bindings and a
native MCP server remain unimplemented.
