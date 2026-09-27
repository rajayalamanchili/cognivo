# Feature Specification: Learner-Facing Explainability UI

**Feature Branch**: `025-learner-explainability-ui`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Learner-facing explainability UI for the Sequencing Agent's question selection and the mastery model: (1) a \"why this question\" in-flow chip sourced from is_fallback + decay + effective-vs-raw p_mastery; (2) a decay-aware mastery bar on the dashboard showing effective (decayed) mastery next to raw score, framed as reversible upkeep; (3) turning last_updated_at \"last practiced\" into an aging warm-colored nudge; (4) a \"why was this marked wrong\" expander showing per-rubric-criterion grading results; (5) a mastery-over-time sparkline per topic from MasteryState history; (6) \"recovered\"/refresh celebration moments when a decayed topic is answered back above threshold; (7) a softened learner-facing version of Milestone 2's Recommendation Agent weak-area report. Encouragement framing throughout: decay is reversible upkeep, never a demotion; show the \"why\" on wins too, not just corrections."

## Context

Constitution Principle V requires that every personalization and grading decision be "logged and explainable" -- that "why was I shown this" and "why was this marked wrong" both have real, traceable answers. Those answers already exist in the system's data (the Sequencing Agent's `is_fallback` flag and the mastery-decay feature's effective-vs-raw mastery, the Grading Agent's per-rubric-criterion results, the `MasteryState` history, and Milestone 2's Recommendation Agent weak-area output) but are not surfaced to the learner anywhere. The mastery-decay feature (spec 024) explicitly spun out its "why this question" UI gap into a separate feature; this is that feature, broadened to cover the other already-logged explanations that have likewise never reached the learner.

This is a read-and-render feature: it exposes decisions the platform already makes and records. It introduces no new personalization or grading logic, and it must never invent numbers the underlying models did not produce.

## Clarifications

### Session 2026-09-27

- Q: A per-criterion grading view already exists today for ordinary (untimed) practice answers, covering both correct/incorrect and both free-text/multi-step, but isn't wired into quiz sessions, timed sessions, placement, or instructor-assigned attempts -- should User Story 3 extend that existing view into the flows missing it, or be dropped as already-delivered? → A: Extend the existing view into quiz (untimed/timed), placement, and instructor-assigned-attempt flows, which lack it today; ordinary practice's existing behavior is the reference implementation, not something to rebuild.
- Q: Should the "refreshed" acknowledgment (User Story 4) fire once, tied to the specific answer that caused the threshold crossing, or be recomputed and potentially re-shown on any later screen where the topic is currently above threshold after having been below? → A: Fire only in the response to the specific answer that caused the crossing, derived from that grading call's before/after mastery; never recomputed or re-shown from later persisted state, and needs no new tracking field.
- Q: Should the "last practiced" warming indicator (FR-007) rely on color alone, or also carry a non-color cue? → A: Color gradient plus a plain-language text label stating elapsed time (e.g. "last practiced 6 months ago") -- color is reinforcement, never the sole signal, consistent with the project's existing accessibility bar (Milestone 10's alt-text gate).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A learner sees why the current question was chosen (Priority: P1)

A learner working through questions sees, alongside each question the Sequencing Agent serves, a short plain-language explanation of why this question came up now -- for example "Reviewing this -- you last practiced it about 6 months ago," "Next step after [prerequisite topic]," or "You're close on this one, one more to lock it in." The explanation reflects the actual selection reason the Sequencing Agent recorded (eligible-pool pick vs. mastered-topic fallback, and, for a fallback pick, how time-decayed the topic was).

**Why this priority**: This is the "why was I shown this" half of Principle V, which has never had a UI for any pick in this product. It closes the exact gap spec 024 identified and deferred. Without it, the platform's most-repeated learner interaction -- being handed a question -- is unexplained.

**Independent Test**: Serve a question via each selection path (eligible-pool pick, and a decay-driven mastered-topic fallback) and confirm the learner sees an explanation that matches the recorded selection reason for that pick, with distinct wording for a decayed-review pick vs. a normal next-step pick.

**Acceptance Scenarios**:

1. **Given** the Sequencing Agent selects a question from the normal eligible pool, **When** the question is shown, **Then** the learner sees a next-step-style explanation naming why this topic is the current step.
2. **Given** the Sequencing Agent falls back to a mastered topic that has decayed since last practice, **When** the question is shown, **Then** the learner sees a review-style explanation that names the elapsed time since last practice and frames it as a refresh, not a failure.
3. **Given** a developer configures the explanation scope to "fallback/decay picks only," **When** an eligible-pool question is shown, **Then** no explanation chip appears; **and** when the scope is "every pick," an explanation appears for both paths.
4. **Given** the selection reason recorded for a pick, **When** the explanation is generated, **Then** the explanation is derived only from that recorded reason and the topic's own mastery data -- it never states a reason the Sequencing Agent did not record.

---

### User Story 2 - A learner sees mastery as reversible upkeep, not a fixed grade (Priority: P1)

On the learner dashboard, each mastered topic shows both its retained (effective, decayed) mastery and its underlying peak mastery, with a "last practiced" indicator that visibly warms as more time passes. The framing throughout is that a decayed topic is refreshable upkeep -- "practice to lock it back in" -- never a demotion or a lost achievement.

**Why this priority**: The mastery-decay feature (spec 024) is backend-only; a learner currently has no way to see that a topic has decayed, why, or that it is recoverable. Showing decay as reversible is the single strongest encouragement lever this feature offers -- it reframes forgetting as normal and fixable rather than as backsliding.

**Independent Test**: Load the dashboard for a learner with one topic mastered recently and one mastered long ago, and confirm the long-untouched topic shows a lower effective mastery than its peak, a warmer "last practiced" indicator, and recovery-oriented framing -- while the recently-practiced topic shows effective mastery equal to its peak.

**Acceptance Scenarios**:

1. **Given** a topic mastered within the decay grace period, **When** the dashboard renders it, **Then** its effective mastery is shown equal to its peak mastery (no decay applied yet).
2. **Given** a topic last practiced well beyond the grace period, **When** the dashboard renders it, **Then** effective mastery is shown below peak mastery, with copy that frames practice as restoring it.
3. **Given** two topics with different elapsed times since last practice, **When** both render, **Then** the one untouched longer shows both a visibly warmer "last practiced" indicator and a text label naming its (longer) elapsed time -- the difference is legible from the text alone, not only the color.
4. **Given** the effective mastery displayed, **When** it is computed, **Then** it equals the decay feature's effective-mastery value for that topic -- the UI does not compute its own decay.

---

### User Story 3 - A learner understands why an answer was marked the way it was, in every flow that grades one (Priority: P2)

A per-criterion "how this was graded" view -- showing, per rubric criterion, which points a free-text or multi-step answer met and which it missed -- already exists for ordinary (untimed) practice, for both correct and incorrect answers. It is not shown in quiz sessions (untimed or timed), placement, or instructor-assigned quiz attempts, which today show only a bare correct/incorrect result. This story extends that same, already-proven view into those remaining flows so a learner gets the identical explanation no matter which flow they answered through.

**Why this priority**: This is the "why was this marked wrong" half of Principle V. The per-criterion grading result is already produced, stored (Principle II), and rendered for practice -- but a learner taking a quiz or a placement assessment, arguably the higher-stakes moments, currently gets no explanation at all. Closing that flow-coverage gap, not rebuilding what practice already does, is this story's actual scope.

**Independent Test**: Grade one free-text (or multi-step) answer that partially satisfies a multi-criterion rubric inside a quiz session, and confirm the learner sees the identical per-criterion breakdown ordinary practice already shows, for both a passing and a failing answer.

**Acceptance Scenarios**:

1. **Given** a graded free-text or multi-step answer inside a quiz session (untimed or timed), placement, or an instructor-assigned quiz attempt, **When** the learner views the result, **Then** each rubric criterion is listed with whether the answer satisfied it, matching the recorded grading result -- the same behavior ordinary practice already has.
2. **Given** a correct answer in any of those flows, **When** the learner views the result, **Then** the criteria it satisfied are shown -- the explainer is not limited to wrong answers, consistent with practice's existing behavior.
3. **Given** a grading result that recorded specific criterion outcomes, **When** the view renders in any flow, **Then** it shows only those recorded outcomes and does not re-grade or re-interpret the answer.
4. **Given** ordinary (untimed) practice, **When** an answer is graded, **Then** its existing per-criterion display is unchanged by this story (regression guard -- this story adds flow coverage, it does not replace practice's existing rendering).

---

### User Story 4 - A learner is celebrated when they refresh a decayed topic (Priority: P2)

When a learner answers a decayed topic and their updated mastery crosses back above the mastery threshold, they see an encouraging "refreshed" moment acknowledging that they brought the topic back up -- reinforcing that the review loop pays off.

**Why this priority**: The mastery-decay feature creates a recover-a-lapsed-topic loop (spec 024, User Story 2), but nothing marks the payoff. A visible "you refreshed this" moment closes the loop emotionally and encourages learners to keep engaging with review picks rather than treating them as chores.

**Independent Test**: Answer a decayed, below-threshold topic correctly enough that the resulting mastery crosses back above threshold, and confirm the learner sees a refreshed acknowledgment; answer one that does not cross the threshold and confirm no false celebration appears.

**Acceptance Scenarios**:

1. **Given** a decayed topic whose mastery is below threshold, **When** the learner answers it and the updated mastery crosses back above threshold, **Then** an encouraging "refreshed" acknowledgment is shown in the response to that specific answer.
2. **Given** a decayed topic answered but whose updated mastery stays below threshold, **When** grading completes, **Then** no "refreshed" acknowledgment is shown.
3. **Given** a topic that was already above threshold, **When** it is answered again, **Then** no "refreshed" acknowledgment is shown (there was nothing to recover).
4. **Given** a topic already refreshed by a previous answer, **When** the learner later revisits the dashboard or answers that topic again, **Then** the acknowledgment does not reappear -- it was shown once, only in the response to the answer that caused the crossing, and is never recomputed from later state.

---

### User Story 5 - A learner sees their mastery trend for a topic (Priority: P3)

On a topic's detail view, the learner sees a small trend line of how their mastery for that topic has moved over time, built from the recorded mastery history, so progress (and recovery after a dip) is visible rather than abstract.

**Why this priority**: Positive reinforcement -- seeing a climbing line, or a dip that recovered, is motivating. It reuses history the platform already records, so it is low-cost, but it is a nice-to-have relative to the core "why" explanations, hence P3.

**Independent Test**: For a topic with several recorded mastery updates over time, confirm the trend line reflects those recorded values in order; for a topic with a single data point, confirm it degrades gracefully.

**Acceptance Scenarios**:

1. **Given** a topic with multiple recorded mastery updates, **When** the trend view renders, **Then** it shows those values in chronological order.
2. **Given** a topic with only one recorded mastery value, **When** the trend view renders, **Then** it renders without error and does not imply a trend that does not exist.
3. **Given** a topic with no recorded mastery ("unknown"), **When** its detail view renders, **Then** no trend line is shown.

---

### User Story 6 - A learner sees a gentle summary of what to shore up (Priority: P3)

The learner can view a softened, encouraging version of their weak-area summary -- "a couple of topics worth shoring up before your next quiz," with concrete next steps -- sourced from the same Recommendation Agent output instructors already see, not a re-computation.

**Why this priority**: It gives learners agency over their own gaps in supportive language, but it depends on framing decisions and is the least tied to the mastery-decay loop that motivated this feature, so it is P3. It must reuse Milestone 2's Recommendation Agent output; re-detecting weak areas here would duplicate that agent and violate Constitution Principles III/IV.

**Independent Test**: For a learner with a known Recommendation Agent weak-area report, confirm the learner-facing view presents the same identified weak areas and next steps in learner-appropriate language, without producing a different set of weak areas than the report contains.

**Acceptance Scenarios**:

1. **Given** a Recommendation Agent weak-area report exists for a learner, **When** the learner opens their summary, **Then** the weak areas and next steps shown correspond to that report's contents.
2. **Given** the report contains no weak areas, **When** the learner opens their summary, **Then** they see an encouraging "nothing flagged right now" state rather than an empty or alarming one.
3. **Given** the learner-facing summary renders, **When** it is produced, **Then** it does not independently recompute weak areas -- it presents the existing report.

---

### Edge Cases

- A pick whose recorded selection reason is missing or unrecognized: the "why this question" chip degrades to no chip (or a neutral "next question") rather than fabricating a reason -- an explanation is never invented (FR-004 / Principle V).
- A quiz or instructor-assigned-attempt question: never shows a "why this question" chip. Discovered during implementation: quiz question selection (`next_quiz_topic`, Milestone 5) is a one-line round-robin over the quiz's chosen topics -- it never calls the Sequencing Agent's eligible-pool/fallback ranking at all, so there is no selection reason to report, not merely one this feature declined to surface. This is FR-004's "omit rather than fabricate" rule applying structurally, not as a defensive edge case.
- A topic that is "unknown" (no mastery state): shows no effective/peak mastery, no decay framing, no trend line, and is never described as decayed.
- An answer graded without a per-criterion rubric breakdown (e.g. a legacy or non-rubric item): the grading expander shows the recorded result at whatever granularity exists and does not fabricate criteria.
- Learner-appropriate language for younger learners: explanation copy respects the platform's existing age-adaptive experience layer (Milestone 17) rather than introducing a second age-adaptation mechanism.
- A "refreshed" threshold crossing and a normal mastery update happening on the same answer: the celebration is driven solely by that specific answer's before/after mastery crossing the threshold from below, computed once in that answer's own response -- never recomputed later, and never re-shown on a subsequent view of the same topic.
- Stateless rendering: all explanations are derived per-request from persisted decisions/data, with no reliance on in-memory session state (Principle IX).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display, for a question served by the Sequencing Agent's next-question picker (ordinary practice and both timed-practice routes), a plain-language explanation of why it was selected, derived from the recorded selection reason for that pick (eligible-pool vs. mastered-topic fallback, and for a fallback pick, its decay standing). Quiz and instructor-assigned quiz attempts use a separate, round-robin topic-selection mechanism (Milestone 5) with no eligible-pool/fallback distinction to report -- FR-001 does not apply to those flows (see Edge Cases).
- **FR-002**: The "why this question" explanation MUST use distinct wording for a decayed-review pick (naming elapsed time since last practice, framed as a refresh) versus a normal next-step pick.
- **FR-003**: The system MUST support a developer-configurable scope switch between explaining every pick and explaining only fallback/decay-driven picks, defaulting to explaining every pick.
- **FR-004**: The system MUST NOT display any selection reason, grading criterion, decay value, or weak area that the underlying model/agent did not record; when a needed record is absent, the corresponding explanation is omitted rather than fabricated.
- **FR-005**: The learner dashboard MUST show, for each mastered topic, both its effective (decayed) mastery and its underlying peak mastery.
- **FR-006**: The effective mastery displayed MUST equal the mastery-decay feature's effective-mastery value for that topic; the UI MUST NOT compute its own decay.
- **FR-007**: The system MUST present a "last practiced" indicator per topic that visibly intensifies as elapsed time since last practice grows, paired with a plain-language text label stating elapsed time -- color intensity alone MUST NOT be the only signal, so the indicator remains legible without relying on color perception.
- **FR-008**: All mastery-decay presentation MUST use recovery/upkeep framing (decay is reversible with practice) and MUST NOT frame a decayed topic as a demotion or lost achievement.
- **FR-009**: The system MUST show the existing per-rubric-criterion grading view (already present for ordinary/untimed practice) for a graded free-text or multi-step answer in every other flow that grades one: quiz sessions (untimed and timed), placement, and instructor-assigned quiz attempts.
- **FR-010**: The grading-results view MUST be available for correct answers as well as incorrect ones, in every flow named in FR-009 -- matching ordinary practice's existing behavior, not a reduced version of it.
- **FR-011**: The system MUST show an encouraging "refreshed" acknowledgment, in the response to the specific answer that causes it, when that answer's grading crosses recorded mastery from below the mastery threshold to above it, and MUST NOT show it otherwise. This acknowledgment MUST NOT be recomputed or re-shown from later persisted state (e.g. a subsequent dashboard view or later answer) and requires no new tracking field.
- **FR-012**: The system MUST show a per-topic mastery trend built from the topic's recorded mastery history, degrading gracefully for single-point and no-history cases.
- **FR-013**: The system MUST offer a learner-facing weak-area summary in supportive language, sourced from Milestone 2's Recommendation Agent output, and MUST NOT independently recompute weak areas.
- **FR-014**: The learner-facing weak-area summary MUST present an encouraging state when no weak areas are flagged.
- **FR-015**: All explanations MUST be produced from persisted decisions/data per request, with no reliance on in-memory session state (Vercel stateless execution).
- **FR-016**: Explanation copy MUST respect the platform's existing age-adaptive experience layer rather than introducing a separate age-adaptation mechanism.
- **FR-017**: No explainability surface may key behavior on a specific subject/content-artifact id (domain-agnostic; Principle III).

### Key Entities *(include if feature involves data)*

- **Selection reason**: The already-recorded rationale for a Sequencing Agent pick (eligible-pool vs. mastered-topic fallback; for a fallback, its decay standing). Read-only input to the "why this question" explanation.
- **Mastery state (effective vs. peak)**: A topic's persisted peak mastery and its decay-derived effective mastery, plus last-practiced time. Source for the dashboard bar, the "last practiced" nudge, and decay framing.
- **Mastery history**: The recorded series of mastery values for a topic over time. Source for the trend view.
- **Grading result (per-criterion)**: The already-recorded rubric-criterion outcomes for a graded answer. Source for the "how this was graded" view.
- **Weak-area report**: Milestone 2's Recommendation Agent output. Source (read-only) for the learner-facing weak-area summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every question served under the default scope, the learner sees a why-selected explanation that matches the recorded selection reason 100% of the time (no fabricated reasons).
- **SC-002**: A learner viewing the dashboard can, within a single glance at a decayed topic, tell that it has decayed and that practice will restore it (verified by usability check: users correctly describe decay as recoverable, not as a demotion).
- **SC-003**: The effective mastery shown on the dashboard matches the mastery-decay feature's computed value for the same topic and evaluation time in 100% of checked cases.
- **SC-004**: A learner can see, for any graded free-text or multi-step answer, which rubric criteria were met and missed -- available for both passing and failing answers, and identical regardless of whether the answer was submitted via practice, a quiz session, placement, or an instructor-assigned attempt.
- **SC-005**: A "refreshed" acknowledgment appears in 100% of below-to-above threshold crossings and in 0% of answers that do not cross the threshold from below.
- **SC-006**: The learner-facing weak-area summary lists exactly the weak areas present in the corresponding Recommendation Agent report (no additions, no omissions) in 100% of checked cases.
- **SC-007**: No explainability surface displays any value that cannot be traced to a persisted model/agent decision (auditable to zero fabricated explanations).

## Assumptions

- The mastery-decay feature (spec 024) is the sole source of effective-mastery values; this feature reads them and does not reimplement or duplicate decay math (Principle I).
- The Sequencing Agent already records, per pick, enough of a selection reason (`is_fallback` and decay standing) to drive FR-001/FR-002; if any needed reason is not yet persisted, persisting it is in scope, but computing selection logic is not.
- FR-001's "why this question" chip applies only to the Sequencing Agent's own next-question picker (ordinary practice, both timed-practice routes) -- not to quiz or instructor-assigned quiz attempts, which select topics via a structurally different round-robin mechanism (Milestone 5) that has no eligible-pool/fallback concept at all. Extending an analogous explanation to quiz's round-robin selection (e.g. "question 3 of 8 in this quiz") is a plausible future idea, not built here.
- The Grading Agent already records per-criterion rubric outcomes (Principle II); this feature surfaces them and does not re-grade.
- Milestone 2's Recommendation Agent is the sole source of weak-area detection; the learner-facing summary reuses its output (Principles III/IV).
- The mastery threshold used for "mastered" and for FR-011's crossing detection is the platform's existing threshold, not a new one introduced here.
- User Story 3 (FR-009/FR-010) reuses ordinary practice's existing per-criterion grading component as-is, extending where it renders rather than building a new one; the component itself needs no behavior change.
- The platform's existing age-adaptive experience layer (Milestone 17) supplies age-appropriate phrasing; this feature adapts copy through it.
- This feature works against existing synthetic/demo and real learner profiles as already permitted; it introduces no new learner-data collection or retention (Principle VIII).
- Presentation is stateless and Vercel-compatible; explanations are derived per request from persisted data (Principle IX).
- Visual/interaction specifics (exact colors, chip placement, animation of the celebration) are design details to be settled in planning; this spec fixes the behavior and framing, not the pixels.
