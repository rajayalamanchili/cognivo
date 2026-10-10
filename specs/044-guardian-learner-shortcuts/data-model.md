# Phase 1 Data Model: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

No new tables, columns, or migrations. This feature changes how existing
entities are *queried and surfaced*, not their shape. Each entity below
already exists; only the "Change for this feature" row is new.

## Enrollment

`backend/src/models/enrollment.py`

| Field | Type | Notes |
|---|---|---|
| `learner_id` | UUID FK -> `learner_profiles` | |
| `roster_id` | UUID FK -> `classroom_rosters` | |
| (unique) | `UniqueConstraint("learner_id", "roster_id")` | Already supports a learner holding more than one enrollment -- a `(learner_id, subject_id)` constraint was never used, so Story 1 requires zero schema change. |

**Change for this feature**: `GET /api/learners/mine` (`learners.py`)
stops collapsing a learner's enrollments to the first `ClassroomRoster`
row the query returns -- it now returns every one, joined the same way
(`Enrollment` joined to `ClassroomRoster`), as a list.

**Response shape change**:

```python
# Before
class MyLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    enrollment: MyLearnerEnrollmentOut | None

# After
class MyLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    enrollments: list[MyLearnerEnrollmentOut]  # [] means "not in a class yet"
```

`MyLearnerEnrollmentOut` itself (`roster_id`, `subject_id`, `grade`) is
unchanged. `status` (`"active"` / `"pending"`, needed by FR-005's
pending-approval tile state, Context Gap 1's mockup note) is already
derivable from the existing `ClassroomRoster.requires_approval` +
`Enrollment`'s own approval state the same way today's single-enrollment
card already computes it -- no new field.

## PracticeSession

`backend/src/models/practice_session.py`

| Field | Type | Notes |
|---|---|---|
| `learner_id` | UUID FK -> `learner_profiles` | Already present; every route in `practice_sessions.py` just never accepted a caller-supplied value for it before this feature -- `start_practice_session` always wrote `get_demo_learner(db).learner_id` here. |
| `subject_id`, `time_limit_seconds`, `status` | unchanged | |

**Change for this feature**: no schema change. `start_practice_session`
accepts a real `learner_id` (research.md §1), gated with
`require_learner_ownership_if_real`; the row it creates is
indistinguishable in shape from one created for the demo learner.

## GradeProgress

`backend/src/models/grade_progress.py`

| Field | Type | Notes |
|---|---|---|
| `learner_id`, `subject_id` | composite PK | |
| `unlocked_grade` | int, monotonic high-water mark | Already real-learner-capable by construction; only `start_placement`'s hardcoded `get_demo_learner` call kept a real learner from ever reaching the code path that creates this row. |

**Change for this feature**: no schema change. `_assign_starting_grade_
if_graded`'s existing `db.get(GradeProgress, (learner_id, subject_id))`
idempotency guard -- already present -- is exactly what makes FR-024's
"Take placement" visibility rule (shown only when no row exists yet) free
to implement: the frontend's "should I show this tile action" check and
the backend's own "should I actually assign a grade" check are the same
underlying fact, queried twice -- once via the same existence check
exposed as the new `has_starting_grade: bool` field on `GET /api/
learners/{learner_id}/enrollments`'s `LearnerEnrollmentOut` (contracts/
api-changes.md's `rosters.py` section), once by the backend's existing
guard -- never two different sources of truth.

## QuizAssignment

`backend/src/models/quiz_assignment.py`

| Field | Type | Notes |
|---|---|---|
| `roster_id` | UUID FK -> `classroom_rosters`, non-nullable | Already present -- every assignment is roster-scoped at creation time. |

**Change for this feature**: `GET /api/learners/{learner_id}/
assignments` (`quiz_assignments.py`) gains an optional `roster_id` query
param, filtering the existing `QuizAssignmentTarget` ⋈ `QuizAssignment`
join by `QuizAssignment.roster_id == roster_id` when provided (research.md
§3). No new field on `AssignmentForLearnerOut` -- the filter happens
server-side, so the response shape is unchanged, just narrower.

## Frontend-only state (no persistence)

**Leave guard** (`frontend/src/lib/leave-guard.ts`, Story 6) -- an
in-memory (not `localStorage`) module-level value, intentionally not a
database entity or even a persisted browser-storage one: it must not
survive a reload (a reload already loses the in-progress question, which
is exactly the state this guards against re-losing silently).

```typescript
interface LeaveGuardState {
  active: boolean;
  message: string; // e.g. "Leaving now starts over with new questions."
}
```

**TutorChat's new prop** (Story 4) -- a plain optional string, not a
stored preference:

```typescript
export interface TutorChatProps {
  sessionId: string;
  onSourcesChange?: (sources: TutorRetrievedPassage[]) => void;
  currentTopicDisplayName?: string; // NEW -- undefined = today's generic prompts
}
```
