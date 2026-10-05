# Contracts: Full K-12 Content Catalog

No contract change for placement, practice, quiz-assignment, or
instructor-dashboard endpoints. See `research.md` Decision 4: every one
of them already resolves `subject_id` against whatever `Subject` rows
exist in the database, with no enumerated allow-list anywhere in route
or service code. Algebra II and Physics become reachable through every
one of those endpoints the moment their content artifact is loaded via
`scripts/load_content_artifact.py` — no request/response contract
changes on either side.

**One real contract change, found necessary during `/speckit-implement`**
(FR-009, Clarifications): `POST /api/rosters` gains an optional
`grade: int | None` request field. `RosterOut`/`RosterSummaryOut` (the
create/get/list response shapes) both gain the same field, echoing back
whatever was stored (`null` for every roster created before this
feature, or one created without declaring a grade).

```
POST /api/rosters
{
  "subject_id": "physics",
  "enrollment_mode": "open",
  "grade": 10            // optional; omit or null for no restriction
}

422 Unprocessable Entity  (grade declared but outside the subject's own grade_bands)
{
  "detail": "roster grade 8 does not overlap subject 'physics''s declared grade_bands [9, 10, 11]"
}
```
