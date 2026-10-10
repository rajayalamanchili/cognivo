# Specification Quality Checklist: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-10
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

- Zero [NEEDS CLARIFICATION] markers: pre-specify investigation
  (`backend/src/api/routes/learners.py`'s own `ponytail:` comment,
  `enrollment.py`'s unique constraint, and the existing Practice/Tutor
  flow code) resolved every ambiguity the user's description raised with
  a reasonable, already-precedented default -- recorded in the
  Assumptions section rather than left open.
- Requirement identifiers (FR-001 through FR-027) reference exact
  existing files/functions in Context for traceability into planning; this
  feature's new backend capability is FR-008 (real-learner support for the
  timed practice-session endpoints) and FR-025-FR-027 (same for
  `start_placement`), both gated the same way other real-learner endpoints
  already are -- everything else stays a UI/response-shape and navigation
  change.
- All items pass on first pass; no spec revision iterations were needed.
- 2026-10-10 clarification session, part 1 (3 questions): replaced Story
  3's "navigate to a separate tutor chat" design with an inline side-panel
  chat on Practice itself (FR-012-FR-019 rewritten accordingly).
- 2026-10-10 clarification session, part 2 (2 questions, 5 total for the
  day): added Story 4 (context-relevant suggested prompts) and
  FR-020-FR-023, revising FR-019's scope to carve out Dashboard's Tutor
  link (now subject-carrying, FR-020) from the Tutor's plain nav-link
  entry (still picker-first).
- Follow-up round, part 1 (1 question, a new `/speckit-clarify` call):
  added Story 5 (FR-024-FR-027), reversing spec 041's prior "real
  placement stays demo-only" decision at the user's explicit request,
  scoped as a fully optional fast-track with no gating of existing
  Practice/Dashboard/Mastery/quiz behavior.
- Follow-up round, part 2 (1 question, same call as a factual "how does
  browser-back behave" investigation): found that Story 2's "Start
  practice" shortcut depended on timed practice-session endpoints that
  are demo-learner-only today (the same gap class Story 5 had just fixed
  for placement) -- inserted FR-008 to close it, renumbering FR-008
  through FR-026 up by one throughout the document. All FR cross-
  references and the Key Entities/Assumptions sections were swept and
  re-verified for consistency after the shift; all checklist items still
  pass.
- Follow-up round, part 3 (1 question): added Story 6 (FR-028-FR-033), a
  confirmation before in-app navigation away from an unsubmitted Practice
  question or Placement answer set -- scoped to in-app navigation only
  per the browser `beforeunload` custom-text limitation surfaced during
  the question. This pass also found and fixed a pre-existing structural
  bug: the `## Clarifications` H2 heading itself was missing (`### Session
  2026-10-10` was nested directly under `## Context`) -- restored. Full
  FR-001-FR-033 cross-reference sweep (every reference resolves, no
  numbering gaps) and heading-structure check both passed after the fix;
  all checklist items still pass.
- `/speckit-analyze` (post-`/speckit-tasks`) found and the user asked to
  fix: FR-025 understated its own backend-gating mechanism relative to
  FR-008's level of detail (now explicit); two wrong in-prose FR
  citations in spec.md (Edge Cases' FR-015 -> FR-017; Key Entities'
  FR-024 -> FR-025 for GradeProgress); one wrong citation in tasks.md's
  T028 (FR-011 -> FR-012); two Assumptions bullets over-citing FR-011/
  FR-019 for Dashboard's own subject-pill switcher (reworded to not
  imply FR coverage that doesn't exist); and the most significant
  finding -- `has_starting_grade` (a new field on `GET /api/learners/
  {learner_id}/enrollments`, needed by tasks.md's T042/T043) had never
  been reconciled back into `contracts/api-changes.md` (which explicitly
  listed `rosters.py` as unchanged) or `plan.md`'s Project Structure.
  All now fixed and cross-checked; all checklist items still pass.
