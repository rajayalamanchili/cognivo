# Data Model: Learner Dashboard

Per research.md §2 and spec.md Key Entities, `DashboardView` is a
**response-shape concept, not a new persisted table** -- assembled at
request time from Milestone 1's existing entities
(`specs/001-domain-agnostic-core/data-model.md`) plus spec 002's
existing `WeakAreaReport` (`specs/002-recommendation-agent/data-model.md`).
No migration in this feature.

## Reused entities (no schema change)

| Entity | Fields this feature reads | Source |
|---|---|---|
| `Subject` | `subject_id`, `display_name`, `validated_at` (gate) | Milestone 1 |
| `Topic` | `topic_id`, `display_name`, `order_index`, `is_entry_level` | Milestone 1 |
| `PrerequisiteEdge` | `from_topic_id`, `to_topic_id` | Milestone 1 |
| `MasteryState` | `p_mastery`, `band` (derived), `update_count` | Milestone 1 |

## Reused response shapes (no change)

| Shape | Endpoint | Used for |
|---|---|---|
| `MasteryStateResponse` | `GET /api/learners/{learner_id}/mastery-state` | FR-001 (per-topic mastery) and the "topics already assessed" half of FR-003 (client-side filter on `status == "scored"`) |
| `RecommendationsResponse` (`WeakAreaReport`) | `GET /api/learners/{learner_id}/recommendations` | FR-002, verbatim |

## New response shapes (this feature)

### SubjectSummary (element of a new list response, not a table)

| Field | Type | Notes |
|---|---|---|
| `subject_id` | string | |
| `display_name` | string | |

One list of these per `GET /api/subjects` call (not per-learner) --
every `Subject` row with `validated_at IS NOT NULL`, ordered by
`subject_id` for a stable render order.

### TopicPriorityPreview (response shape, not a table)

One per (`learner_id`, `subject_id`) request to the new
`topic-priority-preview` endpoint.

| Field | Type | Notes |
|---|---|---|
| `subject_id` | string | |
| `next_topic` | `TopicPreviewEntry` | The Sequencing Agent's current top-priority pick -- identical to what `select_next_topic` would choose for a real next-question request (research.md §1). Always present -- `select_next_topic`'s existing fallback guarantees a chosen topic even when zero topics are strictly eligible. |
| `upcoming_topics` | list of `TopicPreviewEntry` | Up to 3 entries (FR-003/SC-006), the next-ranked entries from the same pool `next_topic` was chosen from, excluding `next_topic` itself. Fewer than 3 only when that pool has fewer than 4 topics total. |
| `is_fallback` | boolean | True when zero topics were strictly eligible (every topic mastered, or none satisfy their prerequisites) and `next_topic`/`upcoming_topics` come from the fallback pool instead -- surfaced so the frontend can, if desired, phrase the section differently for a "you've cleared everything eligible" state (not required by any FR, but cheap to expose since `select_next_topic` already computes it). |

### TopicPreviewEntry

| Field | Type | Notes |
|---|---|---|
| `topic_id` | string | |
| `display_name` | string | |
| `band` | enum: `unknown` \| `struggling` \| `developing` \| `mastered` | Same derivation as `mastery-state`'s `band` field. |
| `p_mastery` | float \| null | `null` when `band = unknown`. |

## DashboardView (frontend-only composition, no backend entity)

Not a wire shape -- assembled in the frontend from three independently-
fetched responses per subject (research.md §5):

```text
DashboardView
 └─ subjects: SubjectSummary[]              <- GET /api/subjects (once)
     └─ for each subject:
         ├─ mastery: MasteryStateResponse            <- FR-001
         ├─ weakArea: RecommendationsResponse         <- FR-002
         └─ pathPreview: TopicPriorityPreview          <- FR-003/FR-004
```

Each of `mastery`, `weakArea`, and `pathPreview` carries its own
independent loading/loaded/error phase (FR-007, FR-008) -- there is no
single "dashboard load succeeded/failed" flag.

## Entity relationship summary

```text
Subject 1---* Topic 1---* PrerequisiteEdge (self-referential)   (existing, read-only here)
Subject 1---* Topic *---1 MasteryState (per learner)             (existing, read-only here)

GET /api/subjects            --> SubjectSummary[]
GET /api/.../mastery-state   --> MasteryStateResponse            (existing, unchanged)
GET /api/.../recommendations --> RecommendationsResponse         (existing, unchanged)
GET /api/.../topic-priority-preview --> TopicPriorityPreview     (NEW)
                                          ├─ next_topic: TopicPreviewEntry
                                          └─ upcoming_topics: TopicPreviewEntry[]
```
