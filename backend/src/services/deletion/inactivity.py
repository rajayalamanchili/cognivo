"""spec 020's inactivity-driven half of the deletion pathway: turns an
overdue `RetentionRecord` into a `DeletionRequest` (FR-005) and keeps
the pre-deletion warning (FR-011) in sync with that same record, both
read by the cron executor's sweep phase (research.md R8).
"""

import datetime
import os
import uuid

from sqlalchemy.orm import Session

from src.models.deletion_request import DeletionRequest
from src.models.enums import AuthorizedByType, DeletionTargetType, RetentionEnrollmentStatus
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.services.notifications.notify import notify_deletion_request

# spec 009 FR-010's 1-year post-inactivity retention ceiling.
INACTIVITY_RETENTION_PERIOD = datetime.timedelta(days=365)
# spec 020 FR-011's pre-deletion warning lead time.
WARNING_LEAD_TIME = datetime.timedelta(days=7)

# Each record's own notify call can block up to the mailer's 10s
# timeout, inside a cron invocation capped at vercel.json's 30s
# maxDuration -- shared with reconcile_inactivity_warnings and
# execute-deletions' own MAX_DELETIONS_PER_RUN-bounded batch in the
# same request. An unbounded loop over every overdue record risked
# exceeding that budget on a large backlog. Capping how many *new*
# notify attempts one invocation makes (same `MAX_..._PER_RUN` pattern
# as `execute.py`'s `MAX_DELETIONS_PER_RUN`) keeps the common case
# safely under budget without needing a schema change; an overdue
# record past the cap is left fully untouched (no `DeletionRequest`
# created yet) for the next run to pick up in full, oldest first.
#
# Residual gap, not closed by this cap: a record whose `DeletionRequest`
# was already committed in a prior run that then died *during* that
# same record's own notify call (not just from a large backlog) stays
# `already_pending` forever with no notification ever recorded --
# `notification_log_entries` carries no link back to the
# `DeletionRequest` that triggered it, so there's no cheap way to tell
# "pending, never notified" apart from "pending, notified, still
# awaiting completion." A durable outbox keyed on that link would close
# this properly; not attempted here given how narrow the window is
# (a kill landing inside one record's own up-to-10s call, not just
# somewhere in the loop).
#
# This also throttles FR-010's own 1-year retention ceiling (a daily
# cron with the "2" default drains an N-record backlog over N/2 days,
# not same-day) -- an accepted trade-off, not an oversight: FR-010's
# own 7-day pre-deletion warning (`reconcile_inactivity_warnings`,
# unaffected by this cap -- no per-record network call) already means
# any backlogged record was warned well before this delay could matter,
# and the env var exists specifically so an operator can raise it if
# their actual backlog size and Resend's typical latency make a bigger
# per-run batch safe. A record whose resolved recipient is `None`
# (unresolvable guardian/instructor -- not possible for real data
# today) is still created but doesn't count against this cap, since it
# never reaches the network call this cap exists to bound.
INACTIVITY_SWEEP_MAX_PER_RUN = int(os.environ.get("INACTIVITY_SWEEP_MAX_PER_RUN", "2"))


def _inactivity_notification_recipient(
    db: Session, record: RetentionRecord
) -> tuple[AuthorizedByType, uuid.UUID, str, bool, str] | None:
    """spec 045 research.md §5 (FR-009): resolves who gets the
    deletion-request confirmation for a system/inactivity-generated
    request. `RetentionAccountType` has no GUARDIAN member (guardians
    aren't inactivity-swept), so this is only ever LEARNER (-> its
    managing guardian, which has no email of its own) or INSTRUCTOR
    (-> itself). `None` if the account/guardian can no longer be
    resolved (not this function's place to raise on)."""
    if record.account_type.value == "learner":
        learner = db.get(LearnerProfile, record.account_id)
        if learner is None or learner.guardian_id is None:
            return None
        guardian = db.get(RealGuardianAccount, learner.guardian_id)
        if guardian is None:
            return None
        return (
            AuthorizedByType.GUARDIAN,
            guardian.guardian_id,
            guardian.email,
            guardian.is_demo,
            # Deliberately generic, not the learner's own display name
            # (plausibly a minor's) -- see deletion.py's identical
            # recipient-resolution helper for the full reasoning.
            "your learner's data",
        )
    instructor = db.get(RealInstructorAccount, record.account_id)
    if instructor is None:
        return None
    return (
        AuthorizedByType.INSTRUCTOR,
        instructor.instructor_id,
        instructor.email,
        instructor.is_demo,
        "your account",
    )


def sweep_inactive_accounts(db: Session) -> int:
    """Creates a `DeletionRequest` for every `RetentionRecord` past
    FR-010's 1-year inactivity ceiling that doesn't already have a
    pending one, sending FR-009's deletion-request confirmation right
    after each, oldest-overdue first. Stops after
    `INACTIVITY_SWEEP_MAX_PER_RUN` *new* notify attempts -- not a cap
    on the query itself, so an already-pending record (cheap to skip)
    never blocks progress toward records that still need creating.
    Returns the count created; anything left over is picked up by the
    next run.

    Commits once per record (spec 045 research.md §5 restructuring,
    /speckit-analyze finding I1) rather than once at the loop's end, so
    a notification is only ever sent for a request that's actually
    persisted, and one record's failure can't roll back a sibling's
    already-sent notification."""
    now = datetime.datetime.now(datetime.UTC)
    cutoff = now - INACTIVITY_RETENTION_PERIOD

    overdue = (
        db.query(RetentionRecord)
        .filter(
            RetentionRecord.enrollment_status == RetentionEnrollmentStatus.INACTIVE,
            RetentionRecord.became_inactive_at.isnot(None),
            RetentionRecord.became_inactive_at <= cutoff,
        )
        .order_by(RetentionRecord.became_inactive_at)
        .all()
    )

    created_count = 0
    notify_attempts = 0
    for record in overdue:
        if notify_attempts >= INACTIVITY_SWEEP_MAX_PER_RUN:
            break
        target_type = DeletionTargetType(record.account_type.value)
        already_pending = (
            db.query(DeletionRequest)
            .filter(
                DeletionRequest.target_type == target_type,
                DeletionRequest.target_id == record.account_id,
                DeletionRequest.completed_at.is_(None),
            )
            .first()
        )
        if already_pending is not None:
            continue
        db.add(
            DeletionRequest(
                target_type=target_type,
                target_id=record.account_id,
                requested_by="system:inactivity-sweep",
            )
        )
        db.commit()
        created_count += 1

        recipient = _inactivity_notification_recipient(db, record)
        if recipient is not None:
            notify_attempts += 1
            account_type, account_id, email, is_demo, target_description = recipient
            notify_deletion_request(
                db,
                is_demo=is_demo,
                account_type=account_type,
                account_id=account_id,
                email=email,
                target_description=target_description,
            )

    return created_count


def reconcile_inactivity_warnings(db: Session) -> int:
    """Two mutually exclusive, ordered checks per `RetentionRecord`
    (research.md R10, FR-011):

    1. `enrollment_status = "active"` -> clear a set warning, checked
       first and unconditionally, regardless of what `became_inactive_at`
       still holds (it can be stale-but-non-null from a prior inactive
       period).
    2. Else, `enrollment_status = "inactive"` and still unwarned -> set
       the warning once inactivity age crosses the 7-day-out threshold.

    The `enrollment_status` guard on branch 2 is required, not
    incidental -- without it, a stale `became_inactive_at` on an active
    record could satisfy the threshold arithmetic too, with no defined
    precedence against branch 1. Returns the count of records whose
    warning state changed this run.
    """
    now = datetime.datetime.now(datetime.UTC)
    warn_at_or_before = now - (INACTIVITY_RETENTION_PERIOD - WARNING_LEAD_TIME)
    changed_count = 0

    reactivated = (
        db.query(RetentionRecord)
        .filter(
            RetentionRecord.enrollment_status == RetentionEnrollmentStatus.ACTIVE,
            RetentionRecord.inactivity_warning_sent_at.isnot(None),
        )
        .all()
    )
    for record in reactivated:
        record.inactivity_warning_sent_at = None
        changed_count += 1

    newly_warned = (
        db.query(RetentionRecord)
        .filter(
            RetentionRecord.enrollment_status == RetentionEnrollmentStatus.INACTIVE,
            RetentionRecord.inactivity_warning_sent_at.is_(None),
            RetentionRecord.became_inactive_at.isnot(None),
            RetentionRecord.became_inactive_at <= warn_at_or_before,
        )
        .all()
    )
    for record in newly_warned:
        record.inactivity_warning_sent_at = now
        changed_count += 1

    db.commit()
    return changed_count
