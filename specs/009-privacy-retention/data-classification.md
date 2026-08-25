# Data Classification: Real Learner & Instructor Data

**Feature**: `009-privacy-retention` | **Date**: 2026-08-22

FR-002's required written classification: every field a real account
would carry once Milestone 7 proper exists, its retention period, and
the event that triggers its deletion. Field shapes reference
`data-model.md`; this document adds the retention/deletion column that
document intentionally leaves out (retention is a policy fact, not a
schema fact).

This is a living document -- update it whenever Milestone 7 proper's
actual implementation introduces a field this classification didn't
anticipate. An unclassified field is not a documentation gap alone; it
is a Principle VIII violation until it's added here.

## RealGuardianAccount

| Field | Category | Retention period | Deletion trigger |
|---|---|---|---|
| `email` | Direct identifier | Life of the account + until every linked `RealLearnerAccount` is also deleted | Guardian's own `DeletionRequest`, or automatic deletion once the last linked learner is deleted and no other learner remains linked |
| `password_hash` | Credential | Life of the account | Same as `email` |

## RealLearnerAccount

| Field | Category | Retention period | Deletion trigger |
|---|---|---|---|
| `display_name` | Direct identifier (a minor's name or chosen display name) | Life of the enrollment, +1 year post-inactivity (FR-010) | `DeletionRequest` (FR-004) or FR-010's automatic post-inactivity deletion |
| Mastery state, assessment events, generated questions (existing tables, FK'd to `learner_id`) | Activity/behavioral data | Same as `display_name` -- **specified** to be deleted in the same cascade, never outliving the identity it's attached to | Same as `display_name` (FR-005's cascade) -- **not yet implemented**: no `ON DELETE CASCADE` and no deletion-execution job exist in code for this table today; a `DeletionRequest` row is created but nothing acts on it. See roadmap.md's "Known gap: real-account deletion pathway is unimplemented" section -- this classification states the required policy, not a working mechanism |
| Tutoring session/exchange transcripts -- `tutoring_sessions`, `tutor_exchanges` (Milestone 9, `specs/012-tutor-agent/data-model.md`), FK'd to `learner_id`; `tutoring_sessions.guardian_id` also FK's to the guardian who opened it | Direct conversational content (a minor's own free-text questions, plus the Tutor Agent's answers) -- higher sensitivity than the existing row above, since it's freeform text rather than structured activity data | Same as `display_name` -- **specified** to be deleted in the same cascade, never outliving the identity it's attached to | Same as `display_name` (FR-005's cascade) -- **not yet implemented**, same gap as the row above (added 2026-08-23 during `012-tutor-agent`'s `/speckit-analyze`, per this document's own "living document" rule, lines 12-15 above; corrected 2026-08-25 after code review on the Milestone 9 promotion PR found this row asserting the cascade as settled fact rather than flagging it as specified-but-unimplemented -- see roadmap.md's "Known gap" section) |

## RealInstructorAccount

| Field | Category | Retention period | Deletion trigger |
|---|---|---|---|
| `email` | Direct identifier | Life of the account, +1 year post-inactivity (FR-010) | `DeletionRequest` or FR-010's automatic deletion. Roster ownership transfers or is deleted per the Edge Case in spec.md (learner data outlives instructor account deletion unless learners are also deleted). |
| `password_hash` | Credential | Life of the account | Same as `email` |

## ClassroomRoster / enrollment linkage

| Field | Category | Retention period | Deletion trigger |
|---|---|---|---|
| `join_code` | Operational (not personal data) | Life of the roster | Roster deletion (follows the owning instructor's account per the Edge Case above) |
| `enrollment_mode` (open/closed) | Operational (not personal data) | Life of the roster | Roster deletion |
| Learner-to-roster membership | Relationship data | Same as the shorter-lived of the two linked accounts | Either side's deletion cascades to remove the membership row |

## DeletionRequest / RetentionRecord

| Field | Category | Retention period | Deletion trigger |
|---|---|---|---|
| `DeletionRequest` rows | Compliance audit record, not personal data itself (post-completion, `target_id` no longer resolves to a live row) | Retained indefinitely as proof the SLA was met -- this is the one category this spec does NOT delete, since it's the evidence a deletion happened, not the deleted person's data itself | Never automatically deleted; a records-retention-policy decision, not a Principle VIII one |
| `RetentionRecord` rows | Compliance metadata | Life of the account it describes | Deleted alongside the account it describes (FR-005's cascade) |

## Explicitly out of scope for real-data collection

Per spec.md's Assumptions and FR-003, this classification deliberately
excludes fields a self-serve, direct-to-minor product might collect but
this one never will under the locked provisioning model: a learner's
own phone number, a learner's own payment information, or any learner-
supplied government ID. If a future feature proposes collecting any of
these, it needs its own addendum to this document before it ships, not
a silent assumption that this spec's approval already covers it.
