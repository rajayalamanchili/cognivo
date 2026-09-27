# Feature Specification: Spaced Repetition / Mastery Decay for Foundational Topics

**Feature Branch**: `035-spaced-repetition-mastery-decay`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Spaced repetition / mastery decay for foundational topics. Today's mastery model (Milestone 1) has no notion of forgetting -- once a topic is marked \"mastered\" it stays mastered forever, which understates real risk for cumulative subjects like STEM (e.g. algebra assumes arithmetic fluency retained years later). This feature should let a previously-mastered topic's mastery score decay over time since last practice, and let that decay resurface the topic through the existing Sequencing Agent rather than inventing a separate scheduler, unless research shows that's not viable."

## Clarifications

### Session 2026-09-27

- Q: Should a learner see, at the moment a decay-driven review question appears, that it's overdue (e.g. "last practiced 6 months ago") -- or is the raw last-practiced date already shown separately on the dashboard (`MasteryTopicOut.last_updated_at`) enough? → A: Yes, add an in-flow explanation.
- Q: Should that in-flow explanation cover every question the Sequencing Agent selects (not just decay/fallback picks), or only fallback/decay-driven ones? → A: Every question -- with a developer-configurable switch between "explain every pick" and "explain only fallback/decay picks."

**Resolution**: This surfaced a real, valid gap -- the Sequencing Agent's question-selection flow (`is_fallback` and now decay) has never had a "why this question" UI anywhere in this product, for any pick, decay or not. Because the chosen scope covers *every* question pick (including the eligible-pool path, which this feature never touches), it is materially larger than mastery decay itself -- a general explainability-UI capability, not a decay-specific one. Per this project's own precedent for scope this size (e.g. instructor-assigned quizzes pulled into their own Milestone rather than piled onto an existing one), it is being spun out into its own feature rather than folded into this spec. This spec's own scope is unchanged from what's already implemented: backend-only, no UI, no dashboard change (see Assumptions below). See the new feature once created for the "why this question" UI itself.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A long-untouched mastered topic is reviewed before a recently-mastered one (Priority: P1)

A learner has mastered two topics with similar mastery scores: one six months ago, never revisited since, and one just last week. When the learner has worked through everything else currently eligible and the platform falls back to picking a mastered topic to review, it should pick the topic that has gone longer without practice, not just whichever happens to have a marginally lower raw score.

**Why this priority**: This is the entire point of the feature -- without it, a topic that was mastered once and never touched again looks indistinguishable from one mastered yesterday, which is exactly the "understates real risk" gap the feature exists to close.

**Independent Test**: Seed two mastered `MasteryState` rows with similar `p_mastery` but very different `updated_at` timestamps, exhaust all other eligible topics, and confirm the Sequencing Agent's mastered-topic fallback selects the more time-decayed one first.

**Acceptance Scenarios**:

1. **Given** two mastered topics with equal raw `p_mastery`, one last practiced well beyond the decay grace period and one practiced within it, **When** the Sequencing Agent falls back to reviewing a mastered topic (no topic is otherwise prerequisite-eligible), **Then** it selects the topic that has gone longer without practice first.
2. **Given** a mastered topic last practiced within the decay grace period, **When** the Sequencing Agent ranks the mastered-review fallback pool, **Then** that topic's effective mastery equals its raw, persisted `p_mastery` exactly -- no decay has been applied yet.
3. **Given** an identical set of mastery states and an identical evaluation time, **When** the fallback ranking runs twice, **Then** it selects the identical topic both times.

---

### User Story 2 - Answering a decayed topic updates mastery exactly like any other answer (Priority: P2)

A learner is served a review question on a topic that has decayed. They answer it. Their mastery score updates the same way it always has -- through the platform's one existing mastery-update mechanism, starting from their true last-known mastery, not from some artificially lowered number.

**Why this priority**: Decay must never leak into the grading/mastery-update math itself, only into which topic gets picked for review -- otherwise this feature would create a second, decay-aware mastery-update code path alongside the existing evidence-based one, which is exactly the kind of special-cased duplication the mastery model's Principle I guarantee ("an explicit, deterministic statistical model," not two of them) exists to prevent.

**Independent Test**: Answer a question on a decayed mastered topic and confirm the resulting `MasteryState.p_mastery` matches what the existing BKT update function would produce from the last-persisted (undecayed) prior -- identical to answering a topic with zero elapsed time.

**Acceptance Scenarios**:

1. **Given** a mastered topic whose effective mastery has decayed, **When** the learner answers it (correct or incorrect), **Then** `MasteryState.p_mastery` updates via the existing mastery-update function using the last-persisted, undecayed `p_mastery` as the starting point -- the decayed value is never used as an input to that update.
2. **Given** that same topic is answered and its `MasteryState.updated_at` refreshes, **When** effective mastery is next computed for it, **Then** decay restarts from the new `updated_at`, not the original one.

---

### Edge Cases

- Two mastered topics decay to the same effective mastery value: fall back to today's existing deterministic tie-break rule for that pool (lowest mastery, then earliest-authored topic) -- decay introduces no new tie-break mechanism.
- A topic with no `MasteryState` row at all ("unknown"): stays exactly "unknown." It is never decayed and never assigned an effective-mastery value.
- A learner whose curriculum keeps producing prerequisite-eligible topics and never exhausts them: never sees a decay-driven review question, because decay only affects the ranking of the mastered-topic fallback pool, which only activates once nothing else is eligible. This is an accepted, in-scope limitation (see Assumptions), not a bug.
- A single topic-ranking call must use one consistent "current time" for every topic it considers, so that two topics aren't compared against subtly different evaluation instants within the same ranking decision.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute an "effective mastery for review ranking" for any topic that has a persisted `MasteryState`, as an explicit, deterministic function of that topic's persisted `p_mastery` and the elapsed time since its `updated_at` -- never an LLM-estimated or manually adjusted value (Constitution Principle I).
- **FR-002**: The decay computation MUST be read-time only. It MUST NOT alter or persist any new value to `MasteryState.p_mastery`, `update_count`, or `consecutive_mastered_observations` -- the evidence-based mastery estimate and its audit trail (Constitution Principle V) remain exactly as answer-driven as they are today.
- **FR-003**: The Sequencing Agent's existing mastered-topic review fallback (the pool it already falls back to when no topic is otherwise prerequisite-eligible) MUST rank that pool by effective (decayed) mastery ascending, lowest first -- replacing its current raw-`p_mastery`-ascending sort for that pool only.
- **FR-004**: All other Sequencing Agent behavior MUST be unaffected by decay: prerequisite-eligibility checks, the ranking of the normal (non-fallback) eligible-topics pool, and any selection where at least one topic is prerequisite-eligible all continue to use raw `p_mastery` exactly as today. Decay changes ranking only inside the already-existing fallback path.
- **FR-005**: A topic's mastery band ("struggling"/"developing"/"mastered") as shown on the learner dashboard, reported by the Recommendation Agent's weak-area report, and used to gate dependent topics' prerequisites MUST continue to be computed from the raw, undecayed `p_mastery`, exactly as today. Decay never changes what counts as "mastered" for any consumer other than the Sequencing Agent's own fallback ranking.
- **FR-006**: Decay MUST apply uniformly to every topic that has a `MasteryState` row, regardless of its position in the topic prerequisite graph -- not restricted to prerequisite-free topics.
- **FR-007**: A topic with no `MasteryState` row ("unknown") MUST NOT be decayed or assigned any effective-mastery value, consistent with the existing rule that "unknown" is never defaulted to a stored value (spec 001 FR-005 precedent).
- **FR-008**: Decay MUST NOT begin until a fixed grace period has elapsed since a topic's `updated_at`. Within the grace period, effective mastery MUST equal raw `p_mastery` unchanged.
- **FR-009**: The grace-period length and the decay curve's rate MUST be fixed global constants applied identically to every topic and learner -- not per-topic-fitted, not per-learner-fitted, not instructor-configurable in this feature -- consistent with the existing BKT mastery model's own fixed-parameter precedent (no real learner data yet exists to fit against, Constitution Principle VIII).
- **FR-010**: Given the same `p_mastery`, `updated_at`, and evaluation timestamp, the decay function MUST always return the identical effective-mastery value (Constitution Principle I). A single topic-ranking or topic-selection call MUST use one consistently captured evaluation timestamp across every topic it ranks.
- **FR-011**: When a learner answers a question on a topic whose effective mastery had decayed, the resulting update MUST use the existing, unmodified mastery-update function with the topic's last-persisted (raw, undecayed) `p_mastery` as the prior. Decay is never fed into that update as an input, and answering a decayed topic follows exactly the same code path as answering any other topic.
- **FR-012**: Ties in effective mastery within the fallback pool MUST break using the existing deterministic tie-break rule already defined for that pool.

### Key Entities

- **Effective Mastery (for review ranking)**: A computed-only value, never persisted, derived from an existing `MasteryState`'s `p_mastery` and elapsed time since `updated_at`. Used exclusively to order the Sequencing Agent's mastered-topic review-fallback pool. Not a new database column, not a new entity with its own lifecycle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given two mastered topics with equal raw mastery, the one last practiced longer ago (beyond the decay grace period) is always selected ahead of the more-recently-practiced one when the Sequencing Agent's mastered-review fallback activates -- 100% of the time, with no manual intervention.
- **SC-002**: A topic practiced within the decay grace period behaves identically to today, with zero change to any existing mastery, sequencing, dashboard, or recommendation-agent behavior -- verified by the full existing regression suite passing unchanged.
- **SC-003**: 100% of answers submitted for a decayed topic update mastery through the exact same mastery-update path as any other answer, with zero new failure modes or decay-aware special cases.
- **SC-004**: Selecting the next topic (including the fallback path) for a given mastery state and evaluation time is fully reproducible -- an identical stored state and identical evaluation time always yields the identical selection, no matter how many times it is repeated.

## Assumptions

- The grace-period length and the decay curve's shape/rate (e.g., an exponential, Ebbinghaus-style forgetting curve) are new fixed global constants, analogous to the mastery model's existing `P_L0`/`P_T`/`P_S`/`P_G_*` constants. Exact numeric values are an implementation detail for `/speckit-plan`, chosen as reasonable defaults absent real learner data to fit against (Constitution Principle VIII), and may be revisited once Milestone 7's real learner data exists.
- Decay's effect is deliberately scoped to only the Sequencing Agent's existing mastered-topic review-fallback ranking. It does not create a new selection pathway that interrupts a learner who still has prerequisite-eligible topics in their normal curriculum progression -- such a learner will never see a decay-driven review question under this feature. Broadening decay to preempt active progression is a distinct, larger change and out of scope here.
- No dashboard, weak-area report, or prerequisite-gating change is included. Mastery band classification everywhere outside the Sequencing Agent's fallback ranking stays computed from raw `p_mastery`, unaffected by this feature. Reaffirmed during clarification (2026-09-27, see Clarifications above): a learner-facing "why this question" explanation was identified as a real, valid gap, but scoped to cover every question pick (not just decay-driven ones) -- large enough to warrant its own feature rather than expanding this one's scope after implementation.
- The evaluation time used for decay is the server's wall-clock time at the moment of the ranking/selection call -- computed lazily per request, not via a background job or cron process, consistent with this project's existing lazy per-request pattern (Milestone 20's timed-session expiry check) and Constitution Principle IX's no-persistent-process constraint on Vercel.
- This feature applies to every topic with a `MasteryState`, not only ones with zero prerequisites -- despite the "foundational topics" framing in the original backlog entry, restricting scope by graph position was considered and rejected as an unnecessary complication with no clear product benefit over applying decay uniformly.
