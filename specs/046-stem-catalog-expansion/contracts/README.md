# Contracts: STEM Catalog Expansion (Remaining Six Subjects)

No contract change for placement, practice, quiz-assignment, roster, or
instructor-dashboard endpoints. See `research.md` Decision 4: every one
of them already resolves `subject_id` against whatever `Subject` rows
exist in the database, with no enumerated allow-list anywhere in route
or service code. `POST /api/rosters`'s `grade` field (added by
Milestone 040's FR-009) already validates against an arbitrary
subject's `GradeBand` rows, not a hardcoded list of the four subjects
that existed when it was built.

All six new subjects become reachable through every one of those
endpoints the moment their content artifact is loaded via
`scripts/load_content_artifact.py` -- no request/response contract
changes on either side, and no new migration.
