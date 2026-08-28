# Specification Quality Checklist: Tutor Agent -- Conversational Delegation, Vector-Grounded Retrieval, and Streaming Responses

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**`/speckit-specify` session (2026-08-23)** -- three clarifications:

1. **FR-009 (delegation architecture)**: the Tutor Agent alone becomes
   a new standalone A2A service; Sequencing and Recommendation stay
   local ADK sub-agents, reached through the backend's existing APIs.
2. **FR-001 (access model)**: guardian-mediated for a real learner,
   plus the seeded demo learner -- matching Milestone 8's precedent, no
   new real-learner login surface.
3. **SC-002 (grounding threshold)**: 90% of a defined test-question set
   must ground in a specific retrieved passage.

**`/speckit-clarify` session (2026-08-23, run after `/speckit-plan`)**
-- four more clarifications, closing gaps the plan phase's research/
data-model work surfaced but hadn't been written back into the spec
itself:

4. **SC-001 (first-token latency)**: was an un-quantified "short,
   bounded time" -- now 3 seconds (p95), matching `research.md` §6's
   already-decided provisional target so spec and plan agree.
5. **FR-013 (rate limiting, new)**: the Tutor Agent's conversational
   endpoint reuses the existing per-learner rate-limit pattern already
   established for free-text answer submission (Milestone 6).
6. **FR-014 (session uniqueness, new)**: at most one active Tutoring
   Session per learner per subject; reopening returns the existing one.
7. **FR-015 (in-flight concurrency, new)**: a new question is rejected
   while the previous one is still streaming, never interleaved,
   queued, or silently cancelled.

Checklist re-validated against the updated spec: still 16/16 passing,
no regressions -- the items above were checked before this session but
against under-specified text (SC-001 in particular); they now pass
against genuinely testable requirements. Ready for `/speckit-tasks`
(plan.md/data-model.md/contracts/api.md were written before this
session's four new/changed requirements -- worth a quick pass to
confirm nothing there contradicts FR-013/014/015 before tasking).

**`/speckit-clarify` session (2026-08-28, branch
`019-tutor-grounding-structured-output`)** -- three clarifications,
prompted by three consecutive PR-review rounds (PRs #42/#44) each
finding a new way the shipped implementation's heuristic parsing of a
bracket-delimited array embedded in the streamed answer text picked
the wrong array or dropped real citations:

8. **FR-016 (grounding channel, new)**: the citation signal moves to a
   structurally separate channel from the answer text -- a dedicated
   terminal tool/function call (e.g. `cite_passages`), not embedded in
   the same prose and parsed back out afterward; MUST NOT loop back to
   the model for a second turn/billed call.
9. **SC-001/SC-004 (latency scope)**: the citation tool call happens
   after the answer text finishes streaming and is explicitly excluded
   from both latency measurements.
10. **Edge Cases (citation-call failure, new)**: a missing/malformed
    citation call after the answer text already streamed persists
    `grounded = false` with an empty passage list and keeps the
    already-streamed text as-is -- no retry, no learner-visible error,
    no retroactive failure marking.

Checklist re-validated against the updated spec: still 16/16 passing,
no regressions. `contracts/api.md`'s "Internal contract: backend ->
Tutor Agent (A2A)" section and `backend/src/services/
tutor_agent_client/client.py`'s heuristic parser both predate FR-016
and will need a `/speckit-plan` pass to bring them in line before
`/speckit-tasks`.
