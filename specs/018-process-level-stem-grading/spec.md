# Feature Specification: Process-Level STEM Grading

**Feature Branch**: `025-process-level-stem-grading`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "process-level STEM grading" -- expanded from roadmap.md's "Out of current roadmap" entry (raised 2026-09-14 during a K-12 STEM gap-analysis session): today's grading (Milestone 1's structured comparison, Milestone 6's free-text rubric grading) is binary against an answer key or a flat set of rubric criteria -- a wrong final answer on a multi-step math/science problem gets no distinction between "the setup was right, there was an arithmetic slip in step 3" and "the underlying concept was misunderstood," which is most of what real STEM mastery diagnosis needs. This feature extends Milestone 6's Grading Agent to grade a multi-step submission step by step, localizing exactly where it first diverges from the expected solution, rather than introducing a new agent or rewriting the mastery model itself.

## Clarifications

### Session 2026-09-14

- Q: Is each step's input a free-text response graded against that
  step's rubric criteria, or a structured/exact-match value, and (once
  raised) does batching change the LLM cost of the free-text option? →
  A: Free-text per step, graded in a single batched LLM call against
  the full step-rubric -- flat LLM cost regardless of step count, the
  same budget as Milestone 6's existing single free-text grade, not one
  call per step.
- Q: What's the maximum acceptable end-to-end time for grading one full
  multi-step submission? → A: 15 seconds, submission received to result
  returned.
- Q: What should happen when a learner's submission has a different
  number of steps than the question's rubric expects? → A: Reject
  before grading with a clear error; no Grading Decision is recorded
  and no mastery update happens.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A wrong answer names the step that went wrong (Priority: P1)

A learner works through a multi-step STEM problem (e.g., solving an
equation, balancing a chemical reaction) and submits their work step by
step rather than only a final answer. Today, an error anywhere in that
process comes back as one undifferentiated "incorrect." Instead, the
learner should see exactly which step first diverged from a correct
solution path, graded against a rubric authored for that purpose --
never a grading model's freeform impression of the work.

**Why this priority**: This is the entire value of the milestone.
Without step-level localization, there is no reason for this feature to
exist, and every other story depends on it working first.

**Independent Test**: Generate a multi-step question for a topic opted
into process-level grading, submit a scripted stepwise answer with a
known-correct setup and a single wrong step, and confirm the grading
result names that specific step rather than returning a bare
"incorrect."

**Acceptance Scenarios**:

1. **Given** a topic opted into process-level grading (FR-001), **When**
   a question is generated for it, **Then** the question carries a
   step-structured rubric -- an ordered list of expected steps, each
   with its own grading criteria -- generated alongside the question,
   before it is ever shown to a learner (Constitution Principle II).
2. **Given** a learner submits a stepwise answer where every step is
   correct, **When** grading completes, **Then** the result is fully
   correct, and the learner's mastery state updates exactly as it would
   for any other correct answer today.
3. **Given** a learner submits a stepwise answer where an early step is
   correct but a later step is wrong, **When** grading completes,
   **Then** the result identifies the specific step index that first
   diverges from the rubric, distinct from a bare "incorrect."
4. **Given** two learners submit byte-identical stepwise answers to the
   same question, **When** both are graded, **Then** both receive an
   identical step-level result (Constitution Principle I).

---

### User Story 2 - The learner can see why a step was marked wrong (Priority: P2)

After a multi-step submission is graded, the learner sees which
specific rubric-defined criterion the diverging step failed -- not just
that it failed -- so "why was this marked wrong" has a real answer at
the step level, the same standard Milestone 6 already holds whole-
question free-text grading to.

**Why this priority**: Constitution Principle V requires every grading
decision be traceable and explainable. A step-level verdict with no
cited reason would be a regression from Milestone 6's existing
criteria-level explainability, not an improvement on it.

**Independent Test**: Submit a stepwise answer with one wrong step,
retrieve the resulting grading decision, and confirm it cites the exact
rubric-defined criterion that step failed.

**Acceptance Scenarios**:

1. **Given** a graded multi-step submission, **When** the learner views
   the result, **Then** each step shows correct or incorrect against
   its own rubric criteria, not only a single aggregate score.
2. **Given** a grading decision recorded for a multi-step submission,
   **When** it is inspected after the fact, **Then** it identifies the
   first-diverging step index and the specific rubric criterion that
   step failed.

---

### User Story 3 - Everything that already works keeps working (Priority: P3)

A topic whose maintainer hasn't authored step-structured rubrics, and
every question type this platform already supports, are completely
unaffected by this feature. The Grading Agent's step-level logic is
deployed and can be fixed independently, exactly the way Milestone 6
already established, without any other agent or service needing to
change.

**Why this priority**: Regression safety and the constitution's
agent-boundary discipline (Principles III, IV, VI) matter, but this
story delivers no new learner-facing value by itself -- it's the
guardrail the first two stories are built inside of.

**Independent Test**: Run Milestones 1-15's existing acceptance suites
unmodified and confirm a non-opted-in topic's grading and mastery-update
behavior is byte-for-byte identical to today; separately, deploy a
step-level scoring change to the Grading Agent alone and confirm no
other agent requires redeployment.

**Acceptance Scenarios**:

1. **Given** a topic that has not opted into process-level grading,
   **When** a learner answers a question for that topic, **Then**
   grading behaves exactly as it does today -- one aggregate result, no
   step breakdown.
2. **Given** the Grading Agent's step-level scoring logic changes,
   **When** it is redeployed per Milestone 6's existing independent-
   redeploy guarantee, **Then** no other agent or service requires
   redeployment.

---

### Edge Cases

- Learner submits fewer or more steps than the rubric expects (jumps
  straight to a final answer, or shows extra work) -- rejected before
  grading per FR-012, no Grading Decision recorded.
- The first step is blank; all steps are blank (must not crash or
  silently pass -- consistent with Milestone 6's existing blank-answer
  handling).
- A later step is logically correct only relative to the learner's own
  (wrong) earlier value -- see FR-006.
- An opted-in topic's generated question has a malformed step rubric
  (zero steps, or a step missing criteria) -- must fail validation, not
  silently degrade to whole-question grading.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A subject's content artifact MUST be able to opt a topic
  into process-level (step-structured) grading. This is additive and
  optional, per topic -- a topic that does not opt in keeps exactly
  today's single-answer grading, unchanged (Constitution Principle III).
- **FR-002**: For every question generated for an opted-in topic, the
  Assessment-Generation Agent MUST generate a step-structured rubric --
  an ordered list of expected steps, each carrying its own grading
  criteria -- alongside the question, before it is ever shown to a
  learner (Constitution Principle II).
- **FR-003**: The system MUST accept a learner's answer to a
  process-level question as a structured, ordered set of per-step
  inputs -- one discrete free-text input per expected step -- rather
  than a single free-text blob that the Grading Agent would otherwise
  have to segment into steps itself.
- **FR-003a**: The Grading Agent MUST grade all steps of a submission
  in a single batched call against the full step-rubric, not one call
  per step -- flat LLM cost regardless of step count, the same budget
  as Milestone 6's existing single free-text grade.
- **FR-004**: The Grading Agent MUST grade a stepwise submission against
  its question's step-structured rubric and identify the first step
  index at which the submission diverges from the expected step, not
  only a whole-question correct/incorrect verdict.
- **FR-005**: When a step is graded incorrect, the Grading Agent MUST
  record which specific rubric-defined criterion that step failed (for
  example, "correct method, arithmetic error" versus "incorrect
  method") -- a distinction authored into the rubric itself at
  generation time, not inferred by a separate freeform judgment
  (Constitution Principle II).
- **FR-006**: When an earlier step is incorrect, the Grading Agent MUST
  stop evaluating subsequent steps and omit them from the result
  entirely (not report them as attempted-and-wrong, and not invent a
  separate "ungraded" status for them) -- a later step is only ever
  graded against the rubric's own expected prior-step value, never
  against whatever value the learner actually carried forward.
- **FR-007**: A graded stepwise submission MUST feed the same
  deterministic mastery-update mechanism already used by every existing
  question type (Constitution Principle I, unchanged) via a single
  aggregate correctness signal derived from the step-level result -- this
  feature does not change the mastery model itself.
- **FR-008**: Every step-level grading decision MUST be reconstructable
  after the fact: which step diverged first, which criterion it failed,
  and the aggregate correctness signal that resulted (Constitution
  Principle V).
- **FR-009**: The Grading Agent's step-level scoring logic MUST remain
  independently deployable from every other agent, per Milestone 6's
  existing A2A boundary justification (Constitution Principle VI). This
  feature extends that agent's existing logic; it does not introduce a
  new agent boundary (Constitution Principle IV).
- **FR-010**: The system MUST reject, at content-authoring/validation
  time, any opted-in topic's question whose rubric is not properly
  step-structured (zero steps, or a step missing its own criteria) --
  consistent with how Milestone 15's validator enforces its own
  structural rule -- rather than silently falling back to whole-question
  grading.
- **FR-011**: Milestones 1-15's full acceptance-scenario suites MUST
  continue to pass unmodified for any topic that has not opted into
  process-level grading.
- **FR-012**: When a submission's step count does not match its
  question's rubric, the system MUST reject it before grading with a
  clear error -- no Grading Decision is recorded and no mastery update
  occurs -- mirroring Milestone 6's existing pattern of rejecting a
  malformed submission (e.g., answer too long) before grading rather
  than guessing intent.

### Key Entities

- **Step Rubric**: An ordered list of expected steps attached to a
  generated question's existing rubric, present only for questions
  belonging to a topic opted into process-level grading. Each step
  carries its own grading criteria, including (per FR-005) a labeled
  failure-mode criterion distinguishing, e.g., a correct method with a
  computational error from an incorrect method entirely.
- **Stepwise Submission**: A learner's answer to a process-level
  question, structured as the same ordered sequence of per-step inputs
  as the rubric it is graded against.
- **Step Grading Result**: The per-step outcome (correct or incorrect)
  attached to an existing Grading Decision for every step up to and
  including the first diverging one -- any step after that is omitted
  from the result entirely, per FR-006, rather than carrying a separate
  "ungraded" status -- plus the first-diverging step index and the
  single aggregate correctness signal derived from it that feeds the
  mastery update.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a multi-step submission with an error in exactly one
  step, the grading result names that specific step -- verified across a
  representative set of error positions (first step, a middle step, the
  last step) -- 100% correctly localized, not merely "incorrect."
- **SC-002**: Two learners submitting byte-identical stepwise answers to
  the same question always receive byte-identical step-level results,
  across repeated runs (determinism, Constitution Principle I).
- **SC-003**: 100% of topics not opted into process-level grading show
  zero behavior change in grading or mastery-update outcomes, measured
  against Milestones 1 and 6's existing acceptance suites.
- **SC-004**: 100% of recorded step-level grading decisions (not a
  sample) can be traced after the fact to the specific rubric criterion
  applied at the diverging step.
- **SC-005**: A step-level scoring-logic change can be deployed to the
  Grading Agent alone and verified live, with zero redeployment of any
  other agent or service, demonstrating this feature preserved
  Milestone 6's existing A2A boundary justification rather than
  eroding it.
- **SC-006**: Grading a full multi-step submission -- from submission
  received to result returned -- completes within 15 seconds, measured
  across the full request path the same way Milestone 6's SC-006 was.

## Assumptions

- Process-level grading is opt-in per topic via the content artifact,
  matching Milestone 15's precedent of additive, per-subject-authored
  scope rather than a forced platform-wide change -- a topic whose
  maintainer hasn't authored step-structured rubrics (e.g., `biology`,
  the same way it stayed ungraded-by-grade-band in Milestone 15) is
  simply unaffected.
- The mastery model's update mechanism (Constitution Principle I) is
  unchanged; only the correctness signal feeding it gains a richer
  source -- an aggregate derived from step results -- for opted-in
  topics.
- Distinguishing an error's *nature* (a sound method with a
  computational slip versus a genuinely incorrect method) is done by
  authoring that distinction directly into each step's rubric criteria
  at generation time (Constitution Principle II), not by a separate
  inference or classification model. This keeps this feature's scope
  distinct from Milestone 11's misconception classifier, which remains
  the owner of open-ended misconception detection from free-form answer
  text.
- This feature extends the existing Grading Agent (Milestone 6); it
  does not introduce a new agent or A2A service (Constitution
  Principle IV).
- Recommendation Agent consumption of step-level evidence, and any
  instructor-dashboard surfacing of step-level results, are plausible
  future integrations and are explicitly out of this milestone's scope.
- A question's step count and per-step expected content are fixed at
  generation time by the rubric; a learner cannot restructure a problem
  into a different number of steps than the rubric expects (see Edge
  Cases -- fewer/more submitted steps than expected is a submission
  validation concern, not a grading-logic concern).
