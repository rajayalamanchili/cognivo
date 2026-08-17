# API Contract: Personalization Evaluation Report

**Feature**: `006-personalization-eval` | **Date**: 2026-08-16

Extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend -- same Vercel Python Function, same stateless-per-request model.
Read-only: this feature adds exactly one endpoint, no mutations.

## `GET /api/evaluation/report`

Returns the most recently published Evaluation Run's Comparison Report
(FR-010, FR-011). No authentication required (Assumptions: read-only,
unauthenticated page). Reads `backend/evaluation/reports/latest.json`
(committed to the repo, deployed read-only with the function --
research.md §8) at request time; never triggers a harness run.

**Path params**: none

**Query params**: none

**Response** `200` (a report has been published):
```json
{
  "published": true,
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
        "sequencing": { "mean": 41.2, "median": 39.5, "non_converged_count": 0, "n": 30 },
        "random": { "mean": 68.7, "median": 65.0, "non_converged_count": 2, "n": 30 },
        "fixed_order": { "mean": 52.3, "median": 50.0, "non_converged_count": 0, "n": 30 }
      }
    }
  ],
  "aggregate": {
    "sequencing": { "mean": 40.1, "median": 38.0, "non_converged_count": 0, "n": 240 },
    "random": { "mean": 66.4, "median": 63.0, "non_converged_count": 9, "n": 240 },
    "fixed_order": { "mean": 51.0, "median": 49.0, "non_converged_count": 1, "n": 240 }
  }
}
```

**Response** `200` (no report has ever been published yet -- FR-011, Edge
Cases; still `200`, not `404`, matching this project's existing
"never-answer-with-a-blank-error-for-an-expected-empty-state" precedent
from spec 002's recommendations endpoint):
```json
{
  "published": false
}
```

The frontend report page (FR-012) renders `aggregate.sequencing` vs.
`aggregate.random` as the plain-language headline result when
`published: true`, and a clear "no evaluation has run yet" state when
`published: false` -- never fabricated figures (FR-011, User Story 4
Acceptance Scenario 2).
