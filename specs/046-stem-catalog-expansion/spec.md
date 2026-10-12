# Feature Specification: STEM Catalog Expansion (Remaining Six Subjects)

**Feature Branch**: `046-stem-catalog-expansion`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "create full catalog of all STEM subjects from grade 1 - Grade 12"

## Scope Note

This project's own roadmap already defines what "full K-12 STEM content
catalog" means for Cognivo: today's four loaded subjects (Algebra I,
Biology, Algebra II, Physics -- the last two shipped as a deliberate
two-subject pilot in `specs/040-k12-content-catalog/`) plus six named,
explicitly-deferred subjects -- **Pre-Algebra, Geometry, Chemistry,
Earth Science, Elementary Math, Elementary Science** (`roadmap.md`,
"Out of current roadmap" section). This spec is that follow-up: it
closes the catalog to those six, bringing the total to ten subjects. It
is **not** a request to add every course a US/Canada K-12 system might
offer (e.g. Calculus, Statistics, Computer Science, Engineering,
Astronomy, Anatomy) -- those were never part of this project's own
catalog definition, have no prior grade-band precedent in this codebase,
and adding them would be new scope requiring its own
`/speckit-clarify`, not a reasonable default. See Assumptions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learner picks from the complete subject catalog (Priority: P1)

A learner (or their guardian, for a real account) starting placement or
practice today chooses from four subjects. With this feature, all ten
subjects -- including, for the first time, elementary-grade content
(grades 1-5) -- are selectable, and every one of them runs through
placement, practice, quizzes, and mastery tracking exactly the way
Algebra I, Biology, Algebra II, and Physics already do.

**Why this priority**: Added content artifacts are inert data until a
learner can actually select and work through them -- this is the entire
point of the feature.

**Independent Test**: Load one new subject's content artifact, start a
placement session against it as the demo learner, and confirm the full
placement to practice to mastery-update loop behaves identically to an
existing subject's, with no code path specific to the new subject.

**Acceptance Scenarios**:

1. **Given** a newly authored and loaded subject content artifact,
   **When** a learner starts placement, **Then** the subject appears as
   a selectable option and placement proceeds exactly as it does for an
   existing subject today.
2. **Given** a learner has an in-progress mastery state in a new
   subject, **When** they answer a question, **Then** mastery updates
   via the same deterministic Sequencing Agent model used for every
   existing subject -- no subject-specific branching.
3. **Given** Elementary Math or Elementary Science (grades 1-5),
   **When** a learner in that grade range starts placement, **Then** the
   existing age-adaptive learner experience (Milestone 19) governs UI
   copy/interaction by grade band exactly as it already does for older
   learners -- no new elementary-specific UI code path.

---

### User Story 2 - Instructor rosters and assigns across the complete catalog (Priority: P2)

An instructor building a roster or assigning a quiz today can target
only the four already-loaded subjects. With this feature, they can
assign from any of the ten loaded subjects, and per-learner results
appear in the instructor dashboard the same way existing subjects'
results do.

**Why this priority**: Instructor-assigned quizzes (Milestone 8) and
the instructor dashboard (Milestone 7) are the primary way a broader
catalog reaches a classroom, not just a solo learner.

**Independent Test**: As an instructor, assign a quiz against a new
subject's topics to a roster, have a guardian complete it on a
learner's behalf, and confirm the result appears per-learner in the
dashboard identically to an existing-subject assignment.

**Acceptance Scenarios**:

1. **Given** a new subject is loaded, **When** an instructor creates a
   quiz assignment, **Then** that subject's topics are selectable in
   the assignment UI alongside the four existing subjects.
2. **Given** an instructor creates a roster declaring a grade (Milestone
   040's FR-009), **When** that grade does not overlap a new subject's
   declared grade band, **Then** roster creation against that subject is
   rejected exactly as it already is for the four existing subjects --
   no new validation logic.

---

### User Story 3 - Content author adds the remaining six subjects, each passing existing validation (Priority: P1)

An LLM-assisted draft produces each new subject's content artifact --
topic graph with prerequisites, a skill definition and difficulty
calibration per topic, standards tags (Milestone 038), and a career
connection (Milestone 039) -- which a human reviewer checks and
approves via the same PR-review process every other content change goes
through, before it is ever loaded. An artifact is rejected at load time
with a specific, actionable error if it fails any check already
enforced on today's four subjects -- never surfaced as a broken question
in front of a learner.

**Why this priority**: Every other story depends on all six new
subjects actually passing the engine's existing content gate. This is
also where almost all of this feature's real cost lives, same as
Milestone 040 -- the engine needs no new code, but each subject needs a
defensible topic graph and calibration, which is authoring effort, not
engineering effort.

**Independent Test**: Author one new subject's `subject.yaml`, run the
existing content-artifact loader/validator against it with zero changes
to validator code, and confirm it is accepted (or rejected with a clear
error) using the exact same checks the four existing subjects are held
to.

**Acceptance Scenarios**:

1. **Given** a new subject artifact missing a required field (e.g. a
   topic with no `skill_definition` or `difficulty_calibration`),
   **When** it is loaded, **Then** the load fails with the same
   validation error class an incomplete existing-subject artifact would
   produce today -- not a new error type.
2. **Given** a new subject artifact whose `prerequisites` form a cycle,
   **When** it is loaded, **Then** the load is rejected before any
   learner can reach it.
3. **Given** a complete, valid new subject artifact, **When** it is
   loaded, **Then** it becomes selectable everywhere the four existing
   subjects already are, with zero changes to
   `check_no_subject_conditionals.py`'s passing state.
4. **Given** Elementary Math or Elementary Science, **When** its
   artifact is authored, **Then** it uses the identical content-artifact
   schema as every secondary-grade subject -- no elementary-specific
   schema field.

---

### Edge Cases

- What happens when a new subject's grade range overlaps an existing
  subject's (e.g. Pre-Algebra and Algebra I both targeting grade 6-7)?
  Subject selection remains by subject identity, not grade -- a
  learner/instructor picks the subject first, matching Milestone 040's
  existing precedent that overlapping grade bands across distinct
  subjects are a non-event by construction.
- What happens when an instructor tries to create a roster whose
  declared grade doesn't overlap a new subject's grade band (e.g. a
  grade-11 roster against Elementary Math)? Roster creation is rejected,
  reusing Milestone 040's existing FR-009 validation unchanged.
- What happens when a new subject has no free-text-capable topics at
  all (e.g. every Elementary Math topic is multiple-choice/numeric)?
  Process-level grading (Milestone 16), notation (Milestone 21), and the
  misconception classifier (Milestone 11) must simply have nothing to
  do for that subject, not error -- matching Milestone 040's existing
  guarantee.
- What happens to the misconception classifier and semantic/guardrail
  caches (Milestones 11, 13, 24) for a brand-new subject with zero
  accumulated `AssessmentEvent` history? They degrade gracefully
  (classifier: no classification produced; caches: every call is a real
  miss until history accumulates), exactly as already guaranteed for
  every prior subject addition -- this feature introduces no new
  cold-start problem.
- What happens if a reviewer rejects a drafted subject's PR? That
  subject's content never loads and is never reachable by any
  learner-facing endpoint -- matching Milestone 040's FR-004 guarantee
  that an unapproved draft is just a file on a branch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support six new K-12 subject content
  artifacts -- **Pre-Algebra, Geometry, Chemistry, Earth Science,
  Elementary Math, and Elementary Science** -- each using the exact same
  content-artifact schema (topics, prerequisites, skill definitions,
  difficulty calibration, standards tags, career connections) as the
  four subjects already loaded, with zero schema changes. These are the
  six subjects named and explicitly deferred in Milestone 040's
  Assumptions and the roadmap's "Out of current roadmap" entry,
  bringing the total loaded catalog to ten subjects.
- **FR-002**: Every new subject's content artifact MUST declare a
  topic/prerequisite graph, a per-topic skill definition, a three-tier
  (easy/medium/hard) difficulty calibration, at least one real standards
  tag (Common Core Math or NGSS, per Milestone 038) per topic, and a
  career connection (per Milestone 039) for every topic -- the same
  completeness bar the four existing subjects are held to today.
- **FR-003**: The content-artifact loader MUST reject, at load time, any
  new subject artifact that fails a check already enforced today
  (missing required field, prerequisite cycle, missing image alt text,
  malformed standards/career-connection entry) -- reusing existing
  validators unchanged, introducing no new validation logic specific to
  any new subject.
- **FR-004**: New subject content MUST be authored as an LLM-assisted
  draft (topic graph, skill definitions, difficulty calibration,
  standards tags, career connections) that a human reviewer checks and
  approves before the artifact is ever loaded -- the same reviewed
  pull-request mechanism every existing content change goes through
  (Milestone 040's FR-004), with no new UI, workflow state, or authoring
  tool. A draft MUST NOT be reachable by any learner-facing endpoint
  until its PR is reviewed and merged.
- **FR-005**: Learners and guardians starting placement or practice MUST
  be able to select any of the six new subjects whose content artifact
  has been successfully loaded, alongside the four already-loaded
  subjects.
- **FR-006**: Instructors MUST be able to build rosters and create quiz
  assignments against any of the six new subjects' topics, with
  per-learner results appearing in the instructor dashboard identically
  to existing-subject assignments -- reusing Milestones 7/8's existing
  mechanisms, no new instructor-facing code path.
- **FR-007**: Every new subject's topics, including any free-text-
  capable ones, MUST flow through the exact same grading,
  misconception-classification, and caching mechanisms as the four
  existing subjects -- no subject-id-keyed conditional anywhere in
  engine source, verified by the existing
  `check_no_subject_conditionals.py` check continuing to pass
  unmodified.
- **FR-008**: A new subject with no accumulated `AssessmentEvent`
  history MUST degrade gracefully everywhere a feature depends on
  accumulated per-subject data (the misconception classifier,
  per-subject semantic/guardrail cache warm-up) -- matching Milestone
  11's existing graceful-degradation guarantee, introducing no new
  cold-start failure mode.
- **FR-009**: Roster creation against any of the six new subjects MUST
  reuse Milestone 040's existing grade-validation behavior (a declared
  `ClassroomRoster.grade` is rejected if it does not overlap the chosen
  subject's declared `grade_bands`) unchanged -- this feature adds no
  new engine logic, only new `grade_bands` data per new subject (see
  Key Entities).
- **FR-010**: Elementary Math and Elementary Science MUST each declare
  `grade_bands: [1, 2, 3, 4, 5]`, with per-topic `grade` values spanning
  that same range -- the first subjects in this catalog to exercise
  grades below 6. The existing age-adaptive learner experience
  (Milestone 19) MUST govern their UI presentation with no new
  elementary-specific adaptation logic.

### Key Entities *(include if feature involves data)*

- **Subject Content Artifact**: An existing entity (Milestone 1,
  extended by Milestones 15/038/039/040) -- this feature adds six more
  instances, not a new shape. Each new instance declares its own
  `subject_id`, `display_name`, `content_version`, `grade_bands`, and an
  ordered list of `Topic` entries. Proposed grade bands (a reasonable
  default per subject, confirmed during authoring, not a hard
  requirement of this spec): Elementary Math `[1-5]`, Elementary Science
  `[1-5]`, Pre-Algebra `[6, 7]`, Geometry `[9, 10]`, Chemistry `[9, 10]`,
  Earth Science `[6]` -- each independently selectable and validated
  only against its own declared band (Milestone 040's FR-009), never
  compared against another subject's band.
- **Topic**: An existing entity -- each new subject's topics carry the
  same fields today's ten-subject (after this feature) catalog's topics
  do: `topic_id`, `display_name`, `grade`, `prerequisites`,
  `skill_definition`, `difficulty_calibration`, `standards`, and
  `career_connection`. No new field is introduced by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The subject catalog grows from today's 4 subjects to 10,
  each independently selectable by a learner and spanning a documented
  grade range from grade 1 through grade 12.
- **SC-002**: 100% of topics in every new subject carry a complete
  skill definition, difficulty calibration, standards tag, and career
  connection at load time -- zero topics ship incomplete, matching the
  bar the four existing subjects already meet.
- **SC-003**: A learner's placement-through-mastery-update flow in any
  new subject, including the two elementary (grades 1-5) subjects, is
  behaviorally indistinguishable from the same flow in an existing
  subject -- verified by the existing acceptance-scenario suites running
  against each new subject with zero subject-specific test scaffolding.
- **SC-004**: An instructor can assign and review results for any new
  subject with zero new UI affordance beyond selecting it from the
  existing subject picker.
- **SC-005**: The full regression suite for every prior milestone and
  shipped feature passes with zero existing test file edited, confirming
  the six new subjects required no engine change -- only new
  content-artifact data.

## Assumptions

- This feature's scope is fixed to the six subjects this project's own
  roadmap already named as the deferred remainder of "Full K-12 STEM
  content catalog" -- Pre-Algebra, Geometry, Chemistry, Earth Science,
  Elementary Math, Elementary Science. The user's broader phrasing ("all
  STEM subjects from grade 1 to grade 12") is interpreted through this
  project's own prior scoping decision (Milestone 040's Assumptions,
  `roadmap.md`'s "Out of current roadmap" section), not through an
  external US/Canada curriculum survey -- courses like Calculus,
  Statistics, Computer Science, Engineering, Astronomy, or Anatomy have
  no precedent anywhere in this codebase and are out of scope for this
  spec. If broader catalog coverage is wanted, that is new scope
  warranting its own `/speckit-clarify` pass, not a default assumed here.
- Per-subject grade bands (Key Entities) are proposed defaults based on
  typical US/Canada course sequencing, following the same
  "real-world-accurate bands, independent of this project's own
  unconventional Algebra I banding" precedent Milestone 040 set. They
  are confirmed during content authoring (FR-004's human-review step),
  not locked by this spec.
- `check_no_subject_conditionals.py`'s existing CI scan remains the
  enforcement mechanism keeping this expansion honest; this feature adds
  no new automated check of its own.
- Elementary Math and Elementary Science (grades 1-5) use the exact same
  content-artifact schema and engine path as every secondary subject --
  Milestone 19's existing age-adaptive layer adapts UI copy/interaction
  by grade band, not a second content model. This is the first time this
  project's catalog reaches below grade 6, which Milestone 19's design
  already anticipated.
- Standards tagging (Milestone 038) and career connections (Milestone
  039) remain a required part of every topic, including elementary
  topics, not an optional enhancement specific to new subjects.
- The per-subject misconception-classifier cold start (Milestone 11) and
  per-subject cache cold start (Milestones 13, 24) are already-accepted,
  already-documented consequences of adding any new subject with no
  grading history yet -- this feature does not attempt to newly solve
  either, matching Milestone 040's same assumption.
- This feature introduces no new grading logic, no new agent, no new A2A
  service, and no new engine-level validation beyond what Milestone 040
  already built for roster-grade checking (FR-009) -- it is a pure
  content-artifact volume expansion validated against the existing
  domain-agnostic engine (Constitution Principle III).
- This feature deliberately closes the roadmap's "Full K-12 STEM content
  catalog" backlog item rather than leaving six subjects perpetually
  deferred -- `roadmap.md` should be updated to strike that entry through
  once this feature ships, the same treatment Milestone 040's partial
  promotion already received.
