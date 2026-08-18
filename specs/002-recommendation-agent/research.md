# Phase 0 Research: Recommendation Agent

No item in Technical Context was marked `NEEDS CLARIFICATION` -- this
feature's platform, language, storage, and testing choices are already
locked by `tech-stack.md` and already implemented in `backend/` from
Milestone 1. Research here is scoped to the feature-specific design
decisions the spec's Clarifications didn't already pin down.

## 1. No LLM call in this agent

**Decision**: The Recommendation Agent's core logic is plain
deterministic Python (`services/recommendation/`), invoked by a thin
orchestration module (`agents/recommendation/agent.py`) registered as
its own ADK-boundary agent per Constitution Principle IV -- but it never
constructs an `LlmAgent`/`LiteLlm` call.

**Rationale**: spec.md's Clarifications (FR-011) require weak-topic
selection, data-sufficiency status, the broad-review threshold, and
prerequisite-gap detection to be fully deterministic; an LLM may only
generate prose *describing* already-computed results, and no FR or SC
in this spec actually requires natural-language prose generation (the
report's citations are structured data: topic ids, event ids, mastery
values -- the frontend consuming this API, per FR-006/data-model.md
below, can render its own copy from that structured shape). Adding an
LLM call the spec doesn't require would be pure scope creep: extra
latency, extra failure surface (a model call that can time out or
return malformed output), and a harder-to-test agent, for a capability
nothing in Milestone 2's Definition of Done asks for.

**Precedent**: The Sequencing Agent's `select_next_topic` (topic
*selection*) is exactly this shape already -- plain Python, no LLM;
only the Assessment-Generation Agent (actual question *content*)
uses `LiteLlm`. Recommendation is structurally closer to Sequencing's
selection logic than to content generation.

**Alternatives considered**: An LLM-generated narrative report
wrapping the structured flags/suggestions. Rejected for the reasons
above; can be revisited in a later milestone (e.g. as part of the
Learner Dashboard, Milestone 4) if a real product need for prose
summaries emerges -- at which point it would need its own grounding
discipline analogous to FR-011, not a silent addition here.

## 2. No new persisted report entity

**Decision**: `WeakAreaReport` and `NextStepSuggestion` (spec.md Key
Entities) are response-shape concepts only, computed fresh from
existing `MasteryState`/`AssessmentEvent`/`Topic`/`PrerequisiteEdge`
rows on every request. No new table stores a report snapshot.

**Rationale**: Nothing in spec.md's FRs or SCs requires retrieving a
past report by id or diffing report history -- the audit trail
requirement (FR-008) is satisfied by the `AssessmentEvent` rows written
as a side effect (see §3), which already persist. Matches the existing
`GET /api/learners/{learner_id}/mastery-state` precedent
(`api/routes/mastery.py`), which is also computed on-demand, not
snapshotted.

**Alternatives considered**: A `weak_area_reports` table for
history/re-fetch. Rejected -- would anticipate Milestone 7's
instructor-aggregation need, which spec.md's Assumptions explicitly
defer ("Instructor-facing aggregation... is deferred to the
instructor-classroom milestone").

## 3. Audit logging shape

**Decision**: Extend `AssessmentEventType` with three new members --
`RECOMMENDATION_REPORT_GENERATED` (one per request; payload carries the
overall `data_sufficiency` verdict and `broad_review_needed` flag),
`WEAK_AREA_FLAGGED` (one per flagged topic; payload carries the citing
`AssessmentEvent` ids and mastery trajectory), and
`NEXT_STEP_SUGGESTED` (one per suggestion; payload carries the
prerequisite chain walked, per FR-007). All written through the
existing `services/audit_log/writer.record_event` -- no new writer.

**Rationale**: Matches the existing one-event-per-decision granularity
(`mastery_updated`, `next_topic_selected`) rather than one big blob
event, so User Story 3's "why was this topic flagged" / "why was this
suggestion made" queries can filter by event type directly. Requires
one Alembic migration adding the three new labels to the Postgres
`assessment_event_type` enum type (same mechanism as the existing
`21a9819b3e22_mastery_state_confirmation_streak.py`-style migrations).

**Alternatives considered**: Reusing an existing generic event type
with a `payload.kind` discriminator. Rejected -- every existing event
type is already granular (`answer_submitted` vs. `mastery_updated` are
two separate rows for one answer, not one event with a `kind` field);
a discriminator would be an inconsistent one-off.

## 4. Reusing existing mastery fields for the two clarified thresholds

**Decision**: FR-002's weak-band check reads `MasteryState.band`
(already the derived `struggling`/`developing`/`mastered` property,
`models/enums.mastery_band_for`); FR-004's per-topic 3-event minimum
reads `MasteryState.update_count` (already incremented on every BKT
update, i.e. already equal to "number of assessment events recorded for
this topic").

**Rationale**: Both fields already exist and already encode exactly
the two numbers this feature's Clarifications locked in (0.4 band
cutoff, 3-event minimum) -- reusing them guarantees this agent's "how
weak" and "how much data" reads can never drift from what Sequencing
and the mastery view already show for the same learner. Introducing a
second, independently-computed copy of either number would risk exactly
the kind of inconsistency Constitution Principle V's explainability bar
exists to prevent.

**Alternatives considered**: A dedicated per-topic assessment-event
`COUNT(*)` query instead of trusting `update_count`. Rejected as
redundant -- `update_count` is already maintained transactionally
alongside every `MasteryState` write (`services/mastery/mastery_tool.py`
... `apply_mastery_update`), so a fresh count query would only be
useful if the two could disagree, which would itself be a bug elsewhere.

## 5. Prerequisite-chain traversal

**Decision**: FR-007's recurse-to-root-cause walk loads
`PrerequisiteEdge` rows the same way `select_next_topic` already does
(one query per subject, held in memory as an adjacency map for the
duration of the request) and walks parent-to-prerequisite links until
hitting a topic that is either `mastered`, has no further prerequisite
edges, or has no `MasteryState` row at all (stops there, reported as
"not yet assessed" per the Clarifications). At any topic along the walk
that has more than one direct prerequisite with more than one
unmastered, the walk follows only the one with the lowest `p_mastery`
(ties broken by ascending `Topic.order_index`) -- the identical
`_sort_key` comparison `agents/sequencing/agent.py` already uses for
topic selection, reused here rather than reimplemented, so exactly one
root-cause prerequisite is ever surfaced per flagged topic (spec.md
FR-007, Clarifications).

**Rationale**: No new cycle-guard is needed beyond what already exists
-- `services/content_artifact/validator.py` rejects any subject whose
topic graph has a cycle at load time (`data-model.md`'s Validation
rule; a subject failing this never gets `validated_at` set, so it's
never servable), so a bounded, terminating walk is guaranteed by an
already-enforced invariant, not something this feature needs to
re-check itself.

**Alternatives considered**: A recursive SQL CTE. Rejected -- subject
topic graphs are small (Milestone 1's two subjects), the adjacency map
is already built in-memory by the identical pattern `select_next_topic`
uses, and a second, SQL-side traversal implementation would be a
second place this logic could drift from Sequencing's.

## 6. FR-009/SC-005 test-independence enforcement

**Decision**: Add an automated check script
(`backend/scripts/check_no_shared_recommendation_sequencing_fixtures.py`),
run in CI alongside the existing `check_no_subject_conditionals.py`
(SC-004's mechanism), that fails if any module under
`tests/integration/recommendation/` is imported by any module under
`tests/integration/test_next_topic_*.py` (or vice versa), and that
`tests/integration/recommendation/scenarios.py` defines no function
whose name collides with a scripted-scenario helper in the Sequencing
test files.

**Rationale**: SC-005 says "verified by inspection" -- but `tech-stack.md`'s
own Testing & evaluation table already establishes the project's
practice of not leaving a constitution-mandated invariant to manual
code review alone once it's mechanically checkable (see the SC-004
row). A one-off `pytest` collection-time assertion is cheap and turns
"inspection" into something CI actually enforces on every PR, not just
at `/speckit-clarify`-adjacent review time.

**Alternatives considered**: Leaving SC-005 as a manual review checklist
item. Rejected -- inconsistent with how SC-004 (the other
mechanically-checkable Constitution-derived SC in this project) is
already handled.
