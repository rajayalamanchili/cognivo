# Research: Grade-Banded Curriculum Scoping

**Feature**: `017-grade-banded-curriculum` | **Date**: 2026-09-06

No `[NEEDS CLARIFICATION]` markers remain in `spec.md` (both were resolved
via `/speckit-specify`'s clarification flow: FR-001 as a new `GradeBand`
entity, FR-004 as "every topic in the grade band reaches mastered").
This file resolves the implementation-shape decisions `/speckit-plan`
itself must make on top of those two answers.

## Decision 1: Grade-banding is all-or-nothing per subject

**Decision**: A content artifact either declares `grade_bands` and gives
every topic a `grade` (a fully graded subject), or declares neither (a
fully ungraded subject, today's exact Milestone 1 behavior). Partial
grading -- some topics graded, some not, within one subject -- is
rejected at content-artifact validation time.

**Rationale**: FR-009 requires ungraded subjects to keep working exactly
as today; the simplest artifact-validation rule that guarantees this
without a third "mixed" code path everywhere (placement's topic
selection, the Sequencing Agent's eligibility filter, the mastery model)
is a hard either/or at load time. A per-topic-optional design would
require every one of those call sites to handle "this topic has no
grade inside an otherwise-graded subject" as its own case, for a
scenario nothing in the spec actually asks for.

**Alternatives considered**: Per-topic-optional grading (rejected --
adds a third code path everywhere for no stated requirement); grade as
a required field with no opt-out (rejected -- directly violates FR-009).

## Decision 2: "Grade-entry topic" generalizes "entry-level topic"

**Decision**: For a graded subject, a topic is a *grade-entry topic* --
the placement-eligible topic for its grade band -- iff every one of its
prerequisites (if any) belongs to a strictly lower grade than the
topic's own grade. For an ungraded subject, `Topic.is_entry_level`
(unchanged: zero prerequisites, subject-wide) is used exactly as today.

**Rationale**: For a subject's lowest declared grade, "every prerequisite
in a strictly lower grade" and "zero prerequisites" are the same set (no
grade exists below the lowest one) -- so this rule is a strict
generalization of `is_entry_level`, not a parallel concept. It reuses
the existing prerequisite graph without adding a stored column: computed
at read time from `Topic.grade` + `PrerequisiteEdge`, mirroring how
`order_index`/prerequisite eligibility are already computed on the fly
elsewhere in `sequencing/agent.py`.

**Alternatives considered**: A separate authored `is_grade_entry` YAML
flag per topic (rejected -- redundant with information the prerequisite
graph + grade already encode, and authorable-but-wrong in a way the
derived rule can't be).

## Decision 3: Starting-grade determination is a pure, testable function

**Decision**: Given the set of grade-entry questions answered in a
placement session (each tagged with its topic's grade and
correct/incorrect), the starting grade is the highest grade G such that
every declared grade from the lowest up through G had its grade-entry
question(s) answered *correctly*, contiguously from the lowest declared
grade. The first grade with a missing or incorrect answer caps the
result at the grade below it; if the lowest declared grade itself isn't
answered correctly, starting grade is the lowest declared grade (a
learner is never placed below a subject's own floor).

Implemented as one pure function,
`determine_starting_grade(correct_by_grade: dict[int, bool], declared_grades: list[int]) -> int`,
with no DB access -- directly satisfies SC-001 (identical inputs, ten
repeated calls, byte-identical output) as a unit test, the same way
`rank_eligible_topics` and `apply_bkt_update` are already tested as pure
functions in this codebase.

**Rationale**: Mirrors FR-004's own "every topic in the grade must be
mastered" contiguous, all-of semantics -- one algorithm, applied twice
(once here for initial placement, once for grade-unlock), rather than
inventing a second scoring rule (e.g. a percentage-correct threshold)
that would need its own justification and its own threshold constant.

**Alternatives considered**: Percentage-correct across all placement
questions regardless of grade (rejected -- doesn't produce a specific
"floor" grade, and a learner could score 80% by acing low grades and
missing high ones, which says nothing about a correct starting point);
majority-vote per grade (rejected -- moot at one grade-entry question
per grade band today, and would need its own justification if a grade
ever gets more than one).

## Decision 4: Skip reuses the same algorithm as an interim read

**Decision**: During placement, a question is skippable only if its
grade is strictly above the learner's *interim* currently-assessed
level -- Decision 3's same function, applied to only the
already-*answered* (not skipped, not yet answered) questions in the
current placement session so far. Skipping never mutates any stored
mastery/grade state; it only decides (a) whether the skip is currently
allowed and (b) which grade band a replacement question is drawn from.

**Rationale**: Reuses Decision 3's function instead of a second,
parallel "how far along is this learner right now" rule -- one
formula, two call sites (final and interim), consistent with this
codebase's existing preference for one canonical eligibility/ranking
rule shared across call sites (`rank_eligible_topics` shared by
`select_next_topic` and `preview_topic_priority`).

## Decision 5: No new "placement session" table -- reuse existing rows

**Decision**: `GeneratedQuestion` gains a nullable `placement_session_id`
column (mirrors the existing `quiz_session_id` column's role for quiz
questions). A placement session's full question set -- including any
skip-driven replacements -- is queryable as
`GeneratedQuestion WHERE placement_session_id = :id`, with
already-answered ones join-able via the existing
`AssessmentEvent(event_type=ANSWER_SUBMITTED)` pattern
`_already_answered` already uses. No new table, no new session-state
concept.

**Rationale**: `start_placement` already mints a `placement_session_id`
UUID and threads it through event payloads; giving `GeneratedQuestion` a
real column for it (rather than only a JSON payload string) makes "all
questions shown in this session" a plain indexed query instead of a JSON
payload scan, matching the precedent `quiz_session_id` already set for
exactly this shape of problem.

**Alternatives considered**: A new `PlacementSession` table tracking
question IDs directly (rejected -- pure duplication of what
`GeneratedQuestion.placement_session_id` + existing `AssessmentEvent`
rows already reconstruct); querying the JSON `payload` field instead of
adding a column (rejected -- works, but is slower and less indexable
than the pattern this codebase already established for quiz sessions).

## Decision 6: Skip is one new endpoint; `submit_placement` is unchanged

**Decision**: `POST /api/placement/{placement_session_id}/skip` is the
only new endpoint. `start_placement`'s selection query changes (grade-
entry topics instead of subject-wide entry-level topics, for a graded
subject) and its response gains a `grade` field per question, but its
request/response *shape* is otherwise unchanged. `submit_placement`
needs **no code change at all**: it already tolerates a partial
`answers` list (any topic with no submitted answer simply reports
`status: "unknown"`), which is exactly FR-007's required behavior for a
skipped question's topic -- the skipped question is simply never
included in the `answers` array the frontend eventually submits.

**Rationale**: The smallest diff that satisfies FR-006/FR-007/SC-004.
Re-deriving "was this skipped" as new stored state on
`submit_placement`'s path would duplicate behavior `submit_placement`
already has for free.

## Decision 7: Grade-unlock check lives in the one function every mastery write already goes through

**Decision**: The FR-004 unlock check (does the learner's `unlocked_grade`
band now have every topic mastered, and if so does a next grade exist)
runs inside `mastery_tool.apply_mastery_update` -- the single function
`placement.py` and `questions.py` both already call for every mastery
write. `MasteryUpdateResult` gains one field, `grade_unlocked: int | None`,
non-null only on the specific call whose posterior update was the one
that completed the grade. Callers log the new `GRADE_UNLOCKED` audit
event only when this field is non-null; the check itself does not write
the audit log (matching this function's existing division of labor --
it never calls `record_event` itself).

**Rationale**: Constitution Principle IV's "fix root causes once, not
per caller" pattern this codebase already follows -- both existing call
sites route through this one function, so gating the check here (rather
than duplicating an "is this grade fully mastered" query in both
`placement.py` and `questions.py`) is the smaller, single-source-of-truth
diff.

## Decision 8: No new agent boundary

**Decision**: All of the above lands as new logic inside the existing
Diagnostic Agent (`grade_entry_topics`), Sequencing Agent (`grade`-aware
eligibility filter in `rank_eligible_topics`), and the mastery tool
(`apply_mastery_update`'s unlock check) -- no new local ADK sub-agent,
no new A2A service.

**Rationale**: Constitution Principle IV's bar (a concrete,
independent-evaluation or independent-versioning need) isn't met here --
grade gating is a deterministic filter over already-existing mastery
state, not a distinct responsibility with its own failure mode or
evaluation criteria. Directly consistent with Milestone 5's precedent
(in-quiz difficulty adjustment as new logic on the existing
Assessment-Generation Agent, not a sixth agent), which spec.md's own
Assumptions already cite as the model to follow here.

## Decision 9: `GradeBand` is a minimal existence table, no extra fields

**Decision**: `GradeBand(subject_id, grade)` -- a composite-PK row per
declared grade, no `display_name` or other metadata column. The UI
label shown to a learner (FR-002) is computed as `f"Grade {grade}"` at
display time, not authored per band.

**Rationale**: Nothing in `spec.md` asks for a grade band to carry any
information beyond its number; adding a `display_name` column and a
content-artifact field for it would be speculative -- reintroduce it
only if a real requirement for custom band labels (e.g. "Grade 6 --
Pre-Algebra") shows up.
