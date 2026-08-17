# Data Model: Real Personalization Signal -- Sequencing Evaluation Harness

**Feature**: `006-personalization-eval` | **Date**: 2026-08-16

Distinguishes **persisted** entities (real Postgres tables, reused from
Milestone 1 -- no new tables/migrations) from **in-memory-only** entities
(exist only for the duration of one harness run) from the **published
artifact** (the committed report file).

## Persisted (reused, no schema changes)

### DemoLearnerProfile (existing table)

One row per simulated learner used by the **Sequencing Agent condition
only** (see research.md §6). `display_name` prefixed `eval-harness-` for
identifiability; `is_demo=True` always (Constitution Principle VIII).
Deleted at the end of the harness run.

### MasteryState (existing table)

Real posterior mastery rows for the Sequencing Agent condition's
synthetic learners, written via the same `apply_bkt_update` function
production uses. Deleted at the end of the harness run, alongside the
`DemoLearnerProfile` rows they reference.

### AssessmentEvent (existing table)

One `NEXT_TOPIC_SELECTED` row per Sequencing Agent condition decision,
written the same way `questions.py`'s real route does (FR-014;
research.md §7, revised post-`/speckit-analyze`). Deleted at the end of
the harness run alongside the `DemoLearnerProfile`/`MasteryState` rows.
Random and fixed-order conditions write none -- they hold no
`demo_learner_id` to attach a row to (§ `SimulatedLearner` below).

## In-memory only (not persisted)

### SyntheticLearnerProfile

A named archetype defining the per-topic true-mastery probability used to
draw ground truth for a batch of simulated learners.

| Field | Type | Notes |
|---|---|---|
| `name` | str | e.g. `"cold-start"`, `"strong-prior"`, `"uneven"`, `"prerequisite-bottleneck"` (research.md §10) |
| `true_mastery_probability(topic, order_index)` | function | Returns the probability this profile's learners truly know a given topic |

### SimulatedLearner

One simulated learner's fixed ground truth, generated once per
(profile, subject, seed) and reused identically across all three
conditions.

| Field | Type | Notes |
|---|---|---|
| `learner_index` | int | Position within the profile's population (0..N-1) |
| `true_mastery` | dict[topic_id, bool] | Fixed for the learner's entire simulated run (research.md §3) |
| `demo_learner_id` | UUID \| None | Set only for the Sequencing Agent condition (research.md §6); `None` for random/fixed-order conditions |

### SimulatedAnswer

One synthetic answer, generated on demand during a condition's run loop.
For the Sequencing Agent condition, each answer's resulting topic
selection is also persisted as a real `AssessmentEvent` row (above);
random/fixed-order conditions' answers stay in-memory only.

| Field | Type | Notes |
|---|---|---|
| `topic_id` | str | Topic the question targeted |
| `question_type` | QuestionType | From `preferred_question_type(topic)`, same helper production uses |
| `correct` | bool | Bernoulli draw per research.md §3 |

### ConditionRunResult

One (profile, subject, condition, learner) outcome.

| Field | Type | Notes |
|---|---|---|
| `profile` | str | |
| `subject_id` | str | |
| `condition` | `"sequencing" \| "random" \| "fixed_order"` | |
| `learner_index` | int | |
| `questions_to_mastery` | int \| None | `None` if non-converged within budget |
| `converged` | bool | |

## Published artifact

### Evaluation Run / Comparison Report (`backend/evaluation/reports/latest.json`)

The single self-describing file an engineer commits to publish a run
(research.md §8). Satisfies FR-013's "which run produced these numbers"
requirement via its own embedded metadata -- no separate log table.

```json
{
  "run_timestamp": "2026-08-16T00:00:00Z",
  "seed": 20260816,
  "profiles": ["cold-start", "strong-prior", "uneven", "prerequisite-bottleneck"],
  "subjects": ["algebra-1", "biology"],
  "population_size_per_profile": 30,
  "max_questions_per_topic_budget": 20,
  "breakdowns": [
    {
      "profile": "cold-start",
      "subject_id": "algebra-1",
      "conditions": {
        "sequencing": { "mean": 41.2, "median": 39.5, "non_converged_count": 0, "non_converged_rate": 0.0, "n": 30 },
        "random": { "mean": 68.7, "median": 65.0, "non_converged_count": 2, "non_converged_rate": 0.067, "n": 30 },
        "fixed_order": { "mean": 52.3, "median": 50.0, "non_converged_count": 0, "non_converged_rate": 0.0, "n": 30 }
      }
    }
  ],
  "aggregate": {
    "sequencing": { "mean": 40.1, "median": 38.0, "non_converged_count": 0, "non_converged_rate": 0.0, "n": 240 },
    "random": { "mean": 66.4, "median": 63.0, "non_converged_count": 9, "non_converged_rate": 0.0375, "n": 240 },
    "fixed_order": { "mean": 51.0, "median": 49.0, "non_converged_count": 1, "non_converged_rate": 0.0042, "n": 240 }
  }
}
```

`breakdowns` has one entry per (profile, subject) pair (8 entries: 4
profiles x 2 subjects); `aggregate` pools across all of them. Figures
above are illustrative placeholders for the schema shape, not real
results. `non_converged_rate` (`non_converged_count / n`) is computed and
stored explicitly, not left for a report consumer to derive -- satisfies
FR-006's "count/rate" wording literally (added post-`/speckit-analyze`,
finding U1).
