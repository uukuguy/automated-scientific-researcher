# Research organization references

Reviewed 2026-11-02/03. Subordinate to PROJECT-DESIGN and D018–D020;
reference patterns are not implementation claims or imported dependencies.

## DeepSeek Super-agent prototype

Primary source: [deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype),
reviewed pin `6337fc823ce20251c8de8085948165c81aaa701e`.
The README describes a research prototype, not a production product; published
source and design discussion do not necessarily implement the same scope.

Useful patterns for ASR:

- Router and per-ticket workers separate coordination from execution; ASR Research
  Leads additionally own scientific reasoning and evidence synthesis.
- A single engine writes state; durable effects run after committed state changes.
  Reuse ASR Control/dispatch identities rather than create another ledger.
- Ticket lifecycle and assignment are independent of conversation session. ASR
  research/hypothesis/trial identities similarly survive runtime replacement.
- Follow-up subscriptions can reach workers directly; avoid routing every message
  through the organizer. Context access does not imply execution authority.
- Distinguish queued/delivered/persisted guidance from actual adoption.
- Version shared and role-specific instructions and record effective inputs.

Do not transfer its execution assumptions unchanged. The inspected worker path
uses broad operator-level permissions; its CLI wrapper is not an OS isolation
boundary. Timeouts on waiting do not necessarily cancel background work or
subagents. ASR must prove actual execution exit before releasing reservations.
Task admission/evaluation in that framework is not independent scientific
validation. Its Harness-specific sessions, inboxes and events are not immediately
compatible with pi, Codex App Server or Grok ACP.

Source anchors at the pin: `docs/007-architecture.md`, `docs/003-execution.md`,
`docs/001-domain.md`, `src/app/effects.ts`, `src/app/delivery.ts`,
`src/app/notices.ts`, `src/app/prompts.ts`, `src/app/sessions.ts`,
`src/executor/background.ts`, `src/executor/dsh.ts`, `src/infra/environment.ts`.
No DeepSeek runtime was installed or executed for this review.

## Shared discussion: native coding-agent runtimes

[User-provided ChatGPT share](https://chatgpt.com/s/t_6ae8a93bb8c88191b30b2bf7906a067f)
was read in the user's already-open Vivaldi page after web retrieval returned a
login shell. Its material recommendation is native Codex App Server and Grok
Build ACP with shared ASR scientific contracts, rather than identical internal
agent implementations. D020 accepts these concrete adapters with pi retained.

Useful: preserve native capabilities, explicit usage unknowns, a small lifecycle
adapter, shared semantic scientific tools, and actual interruption/recovery tests.
Do not equate subscription product ownership, CLI coding, programmatic protocol
handshake and ASR scientific acceptance. User separately confirms local Codex and
Grok login/coding. Claude subscription SDK integration has not been verified by
ASR, despite the share's wording. No future subscription quota announcement is
assumed in budgets. Protocol details are checked against official docs and the
installed version; ACP is not imposed on Codex. See RESEARCHER-RUNTIMES.md.

Comparisons must state whether they match tool capabilities or compare complete
native environments. Neither comparison assigns a vendor permanently to a
scientific role. Preserve evaluation independence and the same original problem.
