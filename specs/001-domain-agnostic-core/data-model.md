# Data Model: Domain-Agnostic Core

**Feature**: `001-domain-agnostic-core` | **Date**: 2026-08-15

All entities are persisted to Postgres on every write (FR-013) -- none
are held only in agent in-process memory, per `tech-stack.md`'s Vercel
deployment constraint. Field names below are illustrative; exact column
types are an implementation-level (`/speckit-tasks`) decision.

## Subject

A top-level namespace for one domain-agnostic content artifact. Exactly
two rows exist in Milestone 1 (Clarifications): `algebra-1`, `biology`.

| Field | Type | Notes |
|---|---|---|
| `subject_id` | string (slug) | Primary key, e.g. `algebra-1`. Never referenced by a subject-id-keyed conditional in engine code (FR-001, SC-004). |
| `display_name` | string | e.g. "Algebra I". |
| `content_version` | string | Version of this subject's content artifact (versioned per `tech-stack.md`'s Content schema section). |
| `validated_at` | timestamp | Set only after passing the load-time cycle/reachability check (FR-002). A subject with no `validated_at` MUST NOT be usable. |

## Topic

Node in a subject's topic graph.

| Field | Type | Notes |
|---|---|---|
| `topic_id` | string (slug) | Primary key, scoped to `subject_id`. |
| `subject_id` | FK -> Subject | |
| `display_name` | string | |
| `is_entry_level` | boolean | True iff this topic has zero prerequisite edges. Drives FR-003's "one placement question per entry-level topic" rule. |
| `skill_definition` | text/JSON | The skill(s) this topic exercises -- content-artifact-owned, never engine logic. |
| `order_index` | integer | The topic's position in the content artifact's authored order (0-based, unique per `subject_id`). Set at load time from the content artifact's declaration order. This is the deterministic tiebreaker the Sequencing Agent's next-topic eligibility rule uses when multiple topics tie on `p_mastery` (FR-006). |

## PrerequisiteEdge

Directed edge in the topic graph: `from_topic` requires `to_topic` be
satisfied first.

| Field | Type | Notes |
|---|---|---|
| `subject_id` | FK -> Subject | |
| `from_topic_id` | FK -> Topic | |
| `to_topic_id` | FK -> Topic | |

**Validation** (FR-002, load-time, not runtime): the directed graph over
a subject's Topics/PrerequisiteEdges MUST be acyclic, and every Topic
MUST be reachable (no prerequisite chain that bottoms out in an
unsatisfiable edge). A subject failing this check MUST NOT receive a
`validated_at` timestamp.

## DifficultyBand

Three fixed bands per topic (Clarifications): `easy`, `medium`, `hard`.
Not its own table -- an enum constraint on `GeneratedQuestion.difficulty`
and on any per-topic difficulty-calibration content the artifact
supplies (e.g. example question templates per band), scoped under that
topic's own content-artifact directory.

## MasteryState

One row per (learner, topic) pair -- only for topics that have received
at least one answer. No row = "unknown" (FR-005); this is a query-time
absence check, never a stored zero or default value.

| Field | Type | Notes |
|---|---|---|
| `learner_id` | FK -> DemoLearnerProfile | |
| `topic_id` | FK -> Topic | |
| `p_mastery` | float `[0,1]` | Current BKT posterior (research.md §1). |
| `band` | enum | Derived, not independently stored authority: `struggling` (< 0.4), `developing` (>= 0.4 and < 0.7), `mastered` (>= 0.7 **and** confirmed per the Mastered-confirmation rule below). Computed from `p_mastery` and `consecutive_mastered_observations` at read time to avoid drift -- never cached, so a band can change immediately after any answer. |
| `updated_at` | timestamp | |
| `update_count` | integer | Number of BKT updates applied; also the count used against the near-duplicate 5-question lookback window (research.md §3) when paired with GeneratedQuestion history. |
| `consecutive_mastered_observations` | integer | Number of consecutive most-recent BKT updates whose posterior was already >= 0.7. Feeds the Mastered-confirmation rule below. Resets to 0 on any update whose posterior falls below 0.7. |

State-transition rule: a row is created on the topic's first answered
question (posterior computed from `p(L0)` and that first observation,
per research.md §1's BKT update), then updated in place on every
subsequent answer for that (learner, topic) pair. Never deleted.

**Mastered-confirmation rule** (SC-005, discovered during Milestone 1
implementation): a posterior `p_mastery >= 0.7` reports as `band =
mastered` only once `consecutive_mastered_observations >= 2` --
i.e. the current update AND the immediately preceding update both
landed at or above 0.7. Below that, a `p_mastery >= 0.7` reads as
`developing`, not `mastered`. This exists because numeric questions'
low guess probability (`p(G)=0.05`, research.md §1) makes a single
correct answer strong enough Bayesian evidence, on its own, to spike
`p_mastery` from `p(L0)=0.3` past 0.7 in one observation. Without this
rule, a degenerate content-blind answer pattern (SC-005) could register
a topic as "mastered" off one lucky guess -- and since a `mastered`
topic is removed from future selection (FR-006's eligibility rule), that
false signal would never get the chance to self-correct on a
subsequent wrong answer. Multiple-choice's higher guess probability
(`p(G)=0.25`) does not exhibit this single-observation spike, but the
confirmation rule applies uniformly to both question types for
consistency and auditability (Constitution Principle V).

**Next-topic eligibility rule** (FR-006, spec.md Clarifications
2026-08-15): a topic is eligible for selection by the Sequencing Agent
if it is `struggling`, `developing`, or has no `MasteryState` row at
all (`unknown`) *and* every `PrerequisiteEdge` pointing to it resolves
to a prerequisite topic whose own `band` is `mastered` -- a prerequisite
counts as "satisfied" only at `mastered`, not merely `touched` or
`developing`. Among eligible topics, selection order is: lowest
`p_mastery` first (`unknown` sorts ahead of any numeric value); ties
broken by ascending `Topic.order_index` -- fully deterministic given
the same `MasteryState` rows and content artifact. If zero
topics are eligible (every topic `mastered` or prerequisite-blocked),
the Sequencing Agent falls back to the `mastered` topic with the
lowest `p_mastery` (review, not a new placement) rather than erroring;
the same lowest-`p_mastery`-then-`order_index` tie-break applies if
multiple `mastered` topics tie during this fallback.

**Difficulty-selection rule** (FR-006): the Sequencing Agent also
derives the generated question's `difficulty` from the selected
topic's current `band` -- a fixed mapping, not within-session adaptive
difficulty (that is Milestone 5's scope, per spec.md Assumptions):

| Selected topic's band | `difficulty` |
|---|---|
| `struggling` or `unknown` | `easy` |
| `developing` | `medium` |
| `mastered` (zero-eligible-topics fallback only) | `hard` |

## GeneratedQuestion

A single dynamically generated structured question.

| Field | Type | Notes |
|---|---|---|
| `question_id` | UUID | Primary key. |
| `learner_id` | FK -> DemoLearnerProfile | Questions are generated per learner, not shared across learners, so the near-duplicate window (FR-008) is meaningful. |
| `topic_id` | FK -> Topic | |
| `difficulty` | enum | `easy` \| `medium` \| `hard`. |
| `question_type` | enum | `multiple_choice` \| `numeric`. |
| `stem` | text | The question text shown to the learner. |
| `options` | JSON, nullable | Present only for `multiple_choice`; ordered list of option strings. |
| `answer_key` | JSON | For `multiple_choice`: the correct option's index/id, graded exact-match. For `numeric`: the correct value plus a per-question relative tolerance (e.g. `±0.5%`) generated by the Assessment-Generation Agent alongside the value itself, not a single global constant (FR-009). Generated together with `stem`/`options`, never after the fact (FR-007, Constitution Principle II). |
| `validation_status` | enum | `pending` \| `valid` \| `invalid` \| `flagged`. Set to `invalid` if the marked-correct option isn't among `options` (FR-007) -- such a question MUST NOT reach `shown_at`. |
| `flagged_by` | FK -> DemoLearnerProfile, nullable | Set when a learner flags the question (FR-011; no instructor role exists in this milestone). |
| `flagged_reason` | text, nullable | |
| `generated_at` | timestamp | |
| `shown_at` | timestamp, nullable | Null until actually displayed; only `valid` questions may have this set. |

**Validation** (FR-007, before `shown_at` may be set): `answer_key`'s
referenced option MUST be present in `options` for `multiple_choice`
questions. A `flagged` question MUST be excluded from all future
selection queries until re-reviewed (FR-011) -- enforced by the
selection query filtering `validation_status != 'flagged'`, not by
deletion (the record must persist for the review workflow FR-011
implies).

## AssessmentEvent

Append-only audit log row -- the FR-010/SC-006 audit trail.

| Field | Type | Notes |
|---|---|---|
| `event_id` | UUID | Primary key. |
| `learner_id` | FK -> DemoLearnerProfile | |
| `event_type` | enum | `placement_question_shown` \| `answer_submitted` \| `mastery_updated` \| `next_topic_selected` \| `question_flagged`. |
| `question_id` | FK -> GeneratedQuestion, nullable | Null for pure sequencing-decision events not tied to a specific question. |
| `topic_id` | FK -> Topic | |
| `payload` | JSON | Event-specific detail -- e.g. for `mastery_updated`: `{prior_p_mastery, posterior_p_mastery, answer_correct, bkt_params_used}`; for `next_topic_selected`: `{candidate_topics_considered, chosen_topic, chosen_topic_band, chosen_topic_p_mastery}`. This is what answers "why was this question chosen" / "why did mastery change this way" (FR-010) after the fact. |
| `created_at` | timestamp | |

This is distinct from, and in addition to, the Langfuse trace emitted
per FR-014/tech-stack.md's Observability section -- `AssessmentEvent`
answers the pedagogical "why," Langfuse answers the technical "what
happened inside the model call."

## DemoLearnerProfile

Milestone 1's lightweight seeded learner (`tech-stack.md`'s Demo account
strategy, "Milestone 1's lighter version" row).

| Field | Type | Notes |
|---|---|---|
| `learner_id` | UUID | Primary key. |
| `display_name` | string | e.g. "Demo Learner". |
| `is_demo` | boolean, non-nullable | MUST be explicitly set `true` at seed time -- never inferred (Constitution Principle VIII). |
| `created_at` | timestamp | |

No real-learner-data path exists in Milestone 1 -- every `learner_id`
referenced above is a `DemoLearnerProfile` row, per spec.md's
Assumptions and Constitution Principle VIII.

## Entity relationship summary

```text
Subject 1---* Topic 1---* PrerequisiteEdge (self-referential via Topic)
Topic 1---* GeneratedQuestion
DemoLearnerProfile 1---* MasteryState *---1 Topic
DemoLearnerProfile 1---* GeneratedQuestion
DemoLearnerProfile 1---* AssessmentEvent
GeneratedQuestion 0..1---* AssessmentEvent
```
