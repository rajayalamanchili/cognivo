# Feature Specification: Grade-Banded Curriculum Scoping

**Feature Branch**: `024-grade-banded-curriculum`

**Created**: 2026-09-06

**Status**: Ready for planning

**Input**: User description: "grade-banded curriculum scoping" -- expanded from roadmap.md's "Known gaps / not yet decided" entry (raised 2026-08-22 after live testing surfaced generated questions as too hard for their intended level): grade-banded curriculum scoping (grades 1-12) per subject, with an initial placement quiz that also assesses a starting grade level (not just per-topic mastery as Milestone 1 does today), placement questions labeled with the grade they represent, a skip option for a question too far above the learner's current assessed level, and progressive grade-level unlocking -- a learner only sees next-grade questions after mastering the current grade's content.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Placement also finds a starting grade, not just per-topic mastery (Priority: P1)

A learner starting a new subject today (Milestone 1) gets one placement
question per entry-level topic and a per-topic mastery estimate, but
nothing tells the system (or the learner) what grade level they're
actually working at -- so a generated question can land far above or
below what the learner can reasonably attempt. Placement must now also
produce an explicit starting grade level per subject, using the same
"real model, not a guess" standard Milestone 1 already holds mastery
estimation to.

**Why this priority**: Every other story in this feature (progressive
unlocking, the skip option) depends on a starting grade level existing
first -- without it there is nothing to unlock from or skip relative to.

**Independent Test**: Load a subject's content artifact, run the
placement flow end to end with a scripted set of answers spanning
multiple grade bands, and confirm the resulting starting grade level is
deterministic given those answers -- rerunning the identical answer
sequence produces an identical starting grade.

**Acceptance Scenarios**:

1. **Given** a subject's content artifact defines one or more grade
   bands, each grouping a set of that subject's existing topics
   (FR-001), **When** a new learner starts placement, **Then** placement questions
   are drawn from more than one grade band and each shown question is
   labeled with the grade it represents.
2. **Given** a learner answers all placement questions, **When** the
   mastery model processes the results, **Then** the learner receives
   both their existing per-topic mastery values (Milestone 1 behavior,
   unchanged) and one explicit starting grade level for the subject.
3. **Given** the exact same sequence of placement answers is replayed,
   **When** placement runs again, **Then** the resulting starting grade
   level is identical to the first run (Constitution Principle I).
4. **Given** a learner's resulting starting grade, **When** the learner
   asks why they were placed at that grade, **Then** the system can
   state which answers drove that placement (Constitution Principle V).

---

### User Story 2 - Progressive grade unlocking (Priority: P1)

Once a learner has a starting grade, they should keep working within
that grade's content until they've actually mastered it -- not be shown
next-grade questions just because a topic-level sequencing decision
happens to reach beyond their current grade.

**Why this priority**: This is the core "too-hard-question" problem
that prompted this feature -- without gating by grade, a learner can
still be shown content above their demonstrated level even after a
correct starting-grade placement.

**Independent Test**: Place a learner at a known starting grade, drive
their mastery below the "current grade mastered" threshold on at least
one required topic, and confirm no next-grade question is ever selected
for them; then bring that topic to mastery and confirm a next-grade
question becomes selectable.

**Acceptance Scenarios**:

1. **Given** a learner placed at grade G, **When** the Sequencing Agent
   selects a learner's next question, **Then** it never selects a
   question from a grade above G unless every topic in grade G's grade
   band has reached the existing "mastered" mastery band (>= 0.7)
   (FR-004).
2. **Given** a learner satisfies grade G's mastery threshold, **When**
   they next request a question, **Then** questions from grade G+1
   become eligible for selection (subject to G+1's own topic
   prerequisites, unchanged from Milestone 1's existing prerequisite
   model).
3. **Given** a learner is already at the highest grade band a subject's
   content artifact defines, **When** they master that grade's content,
   **Then** the system does not attempt to unlock a nonexistent next
   grade and instead reports the subject's grade-progression as
   complete.

---

### User Story 3 - Skip a placement question that's too far above current level (Priority: P2)

A learner taking placement should not be forced to guess at a question
far beyond what they can reasonably attempt just because the placement
flow happened to select it -- they should be able to skip it and
receive an easier one instead.

**Why this priority**: Improves placement accuracy and learner
experience, but the feature is still viable without it (a learner can
simply answer incorrectly and let the mastery model place them lower,
same as Milestone 1's existing behavior) -- so this ships after the
two P1 stories that make grade-banding exist at all.

**Independent Test**: During placement, present a question flagged well
above a learner's currently-assessed grade, invoke the skip action, and
confirm a lower-difficulty replacement question is served without the
skipped question counting as an incorrect answer against mastery.

**Acceptance Scenarios**:

1. **Given** a placement question is labeled with a grade above the
   learner's currently-assessed level, **When** the learner chooses to
   skip it, **Then** a replacement question from a grade at or below
   their current assessed level is served in its place.
2. **Given** a learner skips a placement question, **When** the mastery
   model runs, **Then** the skipped question contributes no mastery
   signal for its topic (neither correct nor incorrect) -- the topic
   remains "unknown" if placement produces no other answered question
   for it.
3. **Given** a learner skips every question offered above their
   starting self-assessment, **When** placement completes, **Then** the
   flow still terminates with a valid starting grade rather than looping
   indefinitely (bounded by the same per-entry-topic question budget
   Milestone 1 already uses).

### Edge Cases

- What happens when a subject's content artifact predates this feature
  and defines no grade metadata at all? The subject MUST continue to
  work exactly as it does today (Milestone 1 behavior, ungraded) rather
  than fail to load -- grade-banding is additive content-artifact
  metadata, not a required field retrofitted onto existing subjects.
- What happens when a topic's prerequisites span grades (e.g. a
  grade-8-labeled topic's prerequisite is labeled grade-6)? Grade
  gating and topic-prerequisite gating both apply -- a topic is
  eligible only when both its own grade is unlocked AND its
  prerequisites (regardless of their grade) are satisfied, same
  combination logic Milestone 1 already uses for prerequisites alone.
- What happens if a learner's mastery on a required grade-G topic later
  regresses below the mastery threshold (e.g. after a run of incorrect
  answers) after grade G+1 was already unlocked? Already-unlocked
  grades stay unlocked -- this feature gates forward progression, it
  does not revoke access already granted, matching the one-directional
  "unlocking" language in the feature's own description.
- How does grade-banding interact with the Milestone 5 Adaptive
  Difficulty Quiz's in-quiz difficulty adjustment? Quiz difficulty
  adjustment continues to operate on the existing easy/medium/hard
  difficulty-calibration bands within a topic; grade is a coarser,
  cross-topic dimension gating which topics are reachable at all, not a
  replacement for within-topic difficulty adjustment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The content artifact schema MUST represent grade as a new
  "grade band" entity: each grade band (1-12) groups a set of that
  subject's existing topics, defined alongside the existing
  prerequisite graph. A topic belongs to exactly one grade band. Per
  Constitution Principle III, grade bands MUST be authored in each
  subject's own content artifact, never as an engine-side conditional
  keyed on subject id.
- **FR-002**: The placement flow MUST select questions spanning more
  than one grade band (not just one question per entry-level topic as
  Milestone 1 does today) and MUST label each placement question shown
  to the learner with the grade it represents.
- **FR-003**: The mastery model MUST produce one explicit starting grade
  level per subject per learner, in addition to (never instead of) the
  existing per-topic mastery values Milestone 1 already produces.
- **FR-004**: The Sequencing Agent's next-question selection MUST treat
  a grade as "mastered" (eligible to unlock the next grade) only once
  every topic belonging to that grade's grade band has reached the
  existing "mastered" mastery band (>= 0.7) -- a deterministic function
  of mastery state per Constitution Principle I, not a judgment call.
- **FR-005**: The Sequencing Agent MUST NOT select a question from a
  grade the learner has not yet unlocked, regardless of what Milestone
  1's existing topic-prerequisite-and-mastery-band selection logic would
  otherwise choose.
- **FR-006**: The system MUST support a learner-initiated skip action on
  a placement question, after which a replacement question at or below
  the learner's currently-assessed grade is served.
- **FR-007**: A skipped placement question MUST NOT be recorded as
  either a correct or incorrect answer for mastery-model purposes --
  its topic remains "unknown" unless a different, answered question
  also targets that topic.
- **FR-008**: The placement flow MUST terminate within a bounded number
  of questions even if every above-level question offered is skipped,
  producing a valid starting grade rather than looping indefinitely.
- **FR-009**: A subject's content artifact that defines no grade
  metadata MUST continue to function exactly as it does today (no
  grade gating applied, no placement grade produced) -- grade-banding
  is opt-in per subject via that subject's own content artifact.
- **FR-010**: Every grade-related mastery-model decision (starting-grade
  assignment, grade-unlock event) MUST be captured in the existing audit
  log with enough detail to reconstruct why the decision was made
  (Constitution Principle V), the same explainability standard
  Milestone 1 already holds topic-level mastery decisions to.

### Key Entities *(include if feature involves data)*

- **Grade band**: a new content-artifact entity (1-12 scale) that
  groups a set of a subject's existing topics; each topic belongs to
  exactly one grade band, defined alongside the existing prerequisite
  graph.
- **MasteryState (extended)**: gains one explicit "current starting/
  unlocked grade" value per subject per learner, alongside the existing
  per-topic mastery values Milestone 1 already tracks -- this feature
  extends, not replaces, that entity.
- **GeneratedQuestion (extended)**: gains a grade label reflecting
  which grade band it was generated for, shown to the learner during
  placement per FR-002.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given an identical sequence of placement answers submitted
  in the same order, the resulting starting grade level is
  byte-for-byte identical across ten repeated runs.
- **SC-002**: Across a full scripted placement-through-first-follow-up
  session, 100% of questions selected for a learner are at or below
  their currently-unlocked grade -- verified by an automated check, not
  by manual inspection.
- **SC-003**: A learner who has not yet met a grade's mastery threshold
  is shown zero questions from the next grade, across 100% of scripted
  test sessions that exercise the unlock boundary.
- **SC-004**: A learner who skips a placement question receives a
  replacement question at or below their current assessed grade in
  under one additional round-trip (no re-placement restart required).
- **SC-005**: A subject's content artifact authored before this feature
  (no grade metadata) continues to pass its existing Milestone 1 test
  suite unmodified -- verified by re-running that suite against this
  feature's changes with zero regressions.
- **SC-006**: Every starting-grade assignment and grade-unlock event in
  a full placement-through-first-follow-up-question session is present
  in the audit log with enough detail to reconstruct why each decision
  was made.

## Assumptions

- Grade-banding is additive to, not a replacement for, Milestone 1's
  existing per-topic BKT mastery model and three-band
  (struggling/developing/mastered) labeling -- a learner still has
  per-topic mastery values exactly as today; grade is a new, coarser
  dimension layered on top, gating which topics are reachable at all.
- The grade scale is fixed at 1-12 per roadmap.md's own framing of this
  feature; a subject need not define all 12 grades, only the ones its
  content actually spans (per FR-009's opt-in behavior).
- This feature stays scoped to the solo-learner flow Milestone 1
  already covers (no instructor role exists yet, per Milestone 1's own
  Assumptions) -- any instructor-facing view of a learner's grade
  progress is Milestone 7 (Instructor Classroom) territory, not this
  feature's.
- The Milestone 5 Adaptive Difficulty Quiz's in-quiz easy/medium/hard
  adjustment is unaffected by this feature (see Edge Cases) -- grade
  gates which topics are reachable; within-topic difficulty adjustment
  keeps working exactly as it does today.
- Whether this feature is implemented as new logic inside the existing
  Diagnostic/Sequencing Agents or would justify a new agent boundary is
  a `/speckit-plan`-level decision, to be weighed against Constitution
  Principle IV's bar (a concrete, statable independent-evaluation or
  independent-versioning need) -- this spec assumes no new agent
  boundary is needed by default, consistent with how Milestone 5's
  quiz-difficulty logic was scoped.
