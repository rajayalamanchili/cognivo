"""spec 020's inactivity-driven half of the deletion pathway: turns an
overdue `RetentionRecord` into a `DeletionRequest` (FR-005) and keeps
the pre-deletion warning (FR-011) in sync with that same record, both
read by the cron executor's sweep phase (research.md R8).
"""

import datetime
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
            f"{learner.display_name}'s data",
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
    after. Returns the count created.

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
        .all()
    )

    created_count = 0
    for record in overdue:
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
