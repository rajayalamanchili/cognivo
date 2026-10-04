# Feature Specification: Full K-12 Content Catalog

**Feature Branch**: `040-k12-content-catalog`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "full K-12 content catalog"

## Clarifications

### Session 2026-10-04

- Q: What grade bands should Algebra II and Physics declare? → A: Real-world-accurate bands — Algebra II grades 9-10, Physics grades 9-11 — independent of this project's own Algebra I banding (6-8).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learner picks from the full subject catalog (Priority: P1)

A learner (or their guardian, for a real account) starting placement or
practice today only ever sees two subjects: Algebra I and Biology. With
the catalog expanded, they can choose from the full set of K-12 subjects
this feature adds, and every one of those subjects runs through
placement, practice, quizzes, and mastery tracking exactly the way
Algebra I and Biology already do.

**Why this priority**: This is the entire point of the feature — without
a learner actually being able to select and work through a new subject,
added content artifacts are inert data no one benefits from.

**Independent Test**: Load one new subject's content artifact, start a
placement session against it as the demo learner, and confirm the full
placement → practice → mastery-update loop behaves identically to
Algebra I's existing behavior, with no code path specific to the new
subject.

**Acceptance Scenarios**:

1. **Given** a newly authored and loaded subject content artifact,
   **When** a learner starts placement, **Then** the subject appears as
   a selectable option and placement proceeds exactly as it does for
   Algebra I or Biology today.
2. **Given** a learner has an in-progress mastery state in a new subject,
   **When** they answer a question, **Then** mastery updates via the
   same deterministic Sequencing Agent model used for every existing
   subject — no subject-specific branching.

---

### User Story 2 - Instructor rosters and assigns across the full catalog (Priority: P2)

An instructor building a roster or assigning a quiz today can only target
Algebra I or Biology topics. With the catalog expanded, they can assign
from any loaded subject, and per-learner results for those subjects
appear in the instructor dashboard the same way existing subjects' results
do.

**Why this priority**: Instructor-assigned quizzes (Milestone 8) and the
instructor dashboard (Milestone 7) are the primary way the breadth of a
larger catalog actually reaches a classroom; without this, the catalog
only helps solo learners.

**Independent Test**: As an instructor, assign a quiz against a new
subject's topics to a roster, have a guardian complete it on a learner's
behalf, and confirm the result appears per-learner in the dashboard
identically to an existing-subject assignment.

**Acceptance Scenarios**:

1. **Given** a new subject is loaded, **When** an instructor creates a
   quiz assignment, **Then** that subject's topics are selectable in the
   assignment UI alongside Algebra I and Biology.
2. **Given** a completed assignment attempt in a new subject, **Then**
   the instructor dashboard's per-learner status/score report renders it
   the same way it renders an Algebra I or Biology assignment.

---

### User Story 3 - Content author adds a new subject that passes existing validation (Priority: P1)

An LLM-assisted draft produces a new subject's content artifact — its
topic graph with prerequisites, a skill definition and difficulty
calibration per topic, standards tags (Milestone 038), and a career
connection (Milestone 039) — which a human reviewer then checks and
approves via the same PR-review process every other content change goes
through, before it is ever loaded. That artifact is rejected at load
time with a specific, actionable error if it fails any check already
enforced on Algebra I and Biology today — never surfaced as a broken
question in front of a learner.

**Why this priority**: Every other story depends on new subjects
actually passing the engine's existing content gate. This is also where
almost all of this feature's real cost lives — the engine itself needs
no new code, but each subject needs a defensible topic graph and
calibration, which is authoring effort, not engineering effort.

**Independent Test**: Author one new subject's `subject.yaml`, run the
existing content-artifact loader/validator against it with zero changes
to validator code, and confirm it is accepted (or rejected with a clear
error) using the exact same checks Algebra I and Biology are held to.

**Acceptance Scenarios**:

1. **Given** a new subject artifact missing a required field (e.g. a
   topic with no `skill_definition` or `difficulty_calibration`),
   **When** it is loaded, **Then** the load fails with the same
   validation error class an incomplete Algebra I/Biology artifact would
   produce today — not a new error type.
2. **Given** a new subject artifact whose `prerequisites` form a cycle,
   **When** it is loaded, **Then** the load is rejected before any
   learner can reach it.
3. **Given** a complete, valid new subject artifact, **When** it is
   loaded, **Then** it becomes selectable everywhere Algebra I and
   Biology already are, with zero changes to `check_no_subject_
   conditionals.py`'s passing state.

---

### Edge Cases

- What happens when a new subject's grade range overlaps an existing
  subject's (e.g. a Pre-Algebra topic and an Algebra I topic both
  targeting grade 8)? Subject selection must remain by subject identity,
  not grade — a learner/instructor picks the subject first, same as
  today's two-subject catalog.
- How does the system handle a roster or learner whose grade band has no
  authored subject yet (e.g. a 3rd-grade roster before elementary content
  exists, or an 8th-grade learner between Algebra I's grade-8 ceiling and
  Algebra II/Physics's grade-9 floor)? The subject-selection surface
  simply shows no options for that grade band — this is a known,
  accepted content-authoring gap (not every grade is covered yet), not a
  defect, and must not crash or silently fall back to a mismatched
  subject.
- What happens when a new subject has no free-text-capable topics at all
  (e.g. every topic is multiple-choice/numeric)? Process-level grading
  (Milestone 16), notation (Milestone 21), and the misconception
  classifier (Milestone 11) must all simply have nothing to do for that
  subject, not error.
- What happens to the misconception classifier and semantic/guardrail
  caches (Milestones 11, 13, 24) for a brand-new subject with zero
  accumulated `AssessmentEvent` history? They must degrade gracefully
  (classifier: no classification produced; caches: every call is a real
  miss until history accumulates) exactly as Milestone 11 already
  guarantees — this feature introduces no new per-subject cold-start
  problem beyond that already-accepted one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support two new K-12 subject content artifacts
  beyond today's Algebra I and Biology — **Algebra II** and **Physics**
  — each using the exact same content-artifact schema (topics,
  prerequisites, skill definitions, difficulty calibration, standards
  tags, career connections) with zero schema changes. These two are a
  deliberate pilot: direct extensions of existing grade bands/subjects
  (Algebra II continues Algebra I's math sequence; Physics is a natural
  secondary-science sibling to Biology), chosen to validate the
  authoring approach (FR-004) and the "zero engine change" claim before
  the remaining six named subjects (Pre-Algebra, Geometry, Chemistry,
  Earth Science, Elementary Math, Elementary Science) are attempted in a
  follow-up feature. Algebra II declares `grade_bands: [9, 10]` and
  Physics declares `grade_bands: [9, 10, 11]` — real-world-accurate
  secondary bands, chosen independently of this project's own
  unconventional Algebra I banding (6-8) so each new subject's standards
  tags (FR-002) can cite real high-school-level Common Core/NGSS codes.
- **FR-002**: Every new subject's content artifact MUST declare a
  topic/prerequisite graph, a per-topic skill definition, a three-tier
  (easy/medium/hard) difficulty calibration, at least one real standards
  tag (Common Core Math or NGSS, per Milestone 038), and a career
  connection (per Milestone 039) for every topic — the same completeness
  bar Algebra I and Biology are held to today, not a reduced bar for new
  content.
- **FR-003**: The content-artifact loader MUST reject, at load time, any
  new subject artifact that fails a check already enforced today
  (missing required field, prerequisite cycle, missing image alt text,
  malformed standards/career-connection entry) — reusing existing
  validators unchanged, introducing no new validation logic specific to
  any new subject.
- **FR-004**: New subject content MUST be authored as an LLM-assisted
  draft (topic graph, skill definitions, difficulty calibration,
  standards tags, career connections) that a human reviewer then checks
  and approves before the artifact is ever loaded. This is content-
  operations process, not a new product capability: the review step is
  a reviewed pull request against the `content/` directory, the same
  mechanism every existing content change already goes through — no new
  UI, workflow state, or authoring tool is built by this feature. A
  draft MUST NOT be reachable by any learner-facing endpoint until its
  PR is reviewed and merged.
- **FR-005**: Learners and guardians starting placement or practice MUST
  be able to select any subject whose content artifact has been
  successfully loaded, not only Algebra I or Biology.
- **FR-006**: Instructors MUST be able to build rosters and create quiz
  assignments against any loaded subject's topics, with per-learner
  results for those assignments appearing in the instructor dashboard
  identically to existing-subject assignments — reusing Milestone 7/8's
  existing mechanisms, no new instructor-facing code path.
- **FR-007**: Every new subject's topics, including any free-text-
  capable ones, MUST flow through the exact same grading, misconception-
  classification, and caching mechanisms as Algebra I and Biology's
  topics today — no subject-id-keyed conditional anywhere in engine
  source, verified by the existing `check_no_subject_conditionals.py`
  check continuing to pass unmodified.
- **FR-008**: A new subject with no accumulated `AssessmentEvent` history
  MUST degrade gracefully everywhere a feature depends on accumulated
  per-subject data (the misconception classifier, per-subject semantic/
  guardrail cache warm-up) — matching Milestone 11's existing graceful-
  degradation guarantee, introducing no new cold-start failure mode.
- **FR-009**: The subject-selection surface (placement start, practice
  start, instructor roster/assignment creation) MUST present only
  subjects whose grade range overlaps the current learner's or roster's
  grade band, consistent with Milestone 17's existing grade-banding
  behavior.

### Key Entities *(include if feature involves data)*

- **Subject Content Artifact**: An existing entity (Milestone 1,
  extended by Milestones 15/038/039) — this feature adds more instances
  of it, not a new shape. Each instance already carries `subject_id`,
  `display_name`, `content_version`, `grade_bands`, and an ordered list
  of `Topic` entries.
- **Topic**: An existing entity — each new subject's topics carry the
  same fields today's Algebra I/Biology topics do: `topic_id`,
  `display_name`, `grade`, `prerequisites`, `skill_definition`,
  `difficulty_calibration`, `standards`, and `career_connection`. No new
  field is introduced by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The subject catalog grows from today's 2 subjects to 4
  (Algebra I: grades 6-8, Biology: ungraded, Algebra II: grades 9-10,
  Physics: grades 9-11), each independently selectable by a learner and
  spanning a documented grade range.
- **SC-002**: 100% of topics in every new subject carry a complete skill
  definition, difficulty calibration, standards tag, and career
  connection at load time — zero topics ship incomplete, matching the
  bar Algebra I and Biology already meet.
- **SC-003**: A learner's placement-through-mastery-update flow in any
  new subject is behaviorally indistinguishable from the same flow in
  Algebra I or Biology — verified by the existing acceptance-scenario
  suites running against the new subject with zero subject-specific
  test scaffolding.
- **SC-004**: An instructor can assign and review results for a new
  subject with zero new UI affordance beyond selecting it from the
  existing subject picker — the instructor-facing surface requires no
  per-subject special case.
- **SC-005**: The full regression suite for every prior milestone
  (Milestones 1-24, plus Standards Alignment and STEM-Career
  Connections) passes with zero existing test file edited, confirming
  the new subjects required no engine change — only new content-artifact
  data.

## Assumptions

- This feature is deliberately a two-subject pilot (Algebra II,
  Physics), not the full eight-subject catalog raised in the roadmap's
  backlog entry. Pre-Algebra, Geometry, Chemistry, Earth Science,
  Elementary Math, and Elementary Science remain explicitly deferred to
  a follow-up feature, gated on this pilot actually proving the LLM-
  assisted-draft-plus-human-review authoring approach and the "zero
  engine change" claim at small scale first.
- `check_no_subject_conditionals.py`'s existing CI scan is the
  enforcement mechanism keeping this expansion honest; this feature adds
  no new automated check of its own.
- Elementary-grade content (Elementary Math/Science) is explicitly
  deferred to the follow-up feature along with Pre-Algebra, Geometry,
  Chemistry, and Earth Science — this feature's pilot (Algebra II,
  Physics) deliberately stays within the secondary grade range Algebra
  I/Biology already cover, so no new grade-adaptation behavior is
  exercised here. When elementary content is attempted, it uses the
  exact same content-artifact schema and engine path as secondary
  content — Milestone 17's existing age-adaptive layer adapts UI
  copy/interaction by grade band, not a second content model.
- LLM-assisted drafting (FR-004) is a content-production detail, not a
  new reviewed workflow state: a draft artifact is just a file on a
  branch until its PR is approved and merged, reusing this project's
  existing PR-review discipline (Constitution Principle X) rather than
  adding a new in-app review queue.
- Standards tagging (Milestone 038) and career connections (Milestone
  039) are already a required part of every topic going forward, not an
  optional enhancement specific to new subjects.
- The per-subject misconception-classifier cold start (Milestone 11) and
  per-subject cache cold start (Milestones 13, 24) are already-accepted,
  already-documented consequences of adding any new subject with no
  grading history yet — this feature does not attempt to newly solve
  either.
- This feature introduces no new grading logic, no new agent, and no new
  A2A service: it is a content-artifact volume expansion validated
  against the existing domain-agnostic engine (Constitution Principle
  III), not a new engineering capability.
