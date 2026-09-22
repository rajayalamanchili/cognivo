"""Vercel Cron-triggered demo-data reset (tech-stack.md's Demo account
reset row, FR-015/SC-005, T057b).

Vercel Cron sends a `GET` request to this path on its configured
schedule (`vercel.json`'s `crons` array) with `Authorization: Bearer
$CRON_SECRET` (Vercel's own documented cron-authentication mechanism).
Verified via `hmac.compare_digest`, fails closed if `CRON_SECRET` isn't
configured -- the same shared-secret pattern this project already locks
for A2A inbound auth (tech-stack.md), applied here so an arbitrary
public caller can't trigger a reset of the live demo state on demand.
"""

import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from scripts.reset_demo_data import reset_demo_data
from src.db import get_db
from src.models.deletion_request import DeletionRequest
from src.models.enums import DeletionTargetType
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.deletion.execute import MAX_DELETIONS_PER_RUN, execute_deletion
from src.services.deletion.inactivity import reconcile_inactivity_warnings, sweep_inactive_accounts
from src.services.misconception.classify import run_classification_batch

logger = logging.getLogger(__name__)

router = APIRouter()

_DELETION_TARGET_MODEL: dict[DeletionTargetType, type] = {
    DeletionTargetType.LEARNER: LearnerProfile,
    DeletionTargetType.GUARDIAN: RealGuardianAccount,
    DeletionTargetType.INSTRUCTOR: RealInstructorAccount,
}


def _require_cron_secret(authorization: str | None) -> None:
    expected_secret = os.environ.get("CRON_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET not configured")

    provided = (authorization or "").removeprefix("Bearer ")
    if not hmac.compare_digest(provided, expected_secret):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/api/cron/reset-demo-data")
def reset_demo_data_route(authorization: str | None = Header(default=None)) -> dict:
    _require_cron_secret(authorization)
    reset_demo_data()
    return {"status": "ok"}


@router.get("/api/cron/classify-misconceptions")
def classify_misconceptions_route(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict:
    """Spec 013's scheduled classification job (contracts/api.md,
    research.md §3) -- mirrors `reset_demo_data_route`'s auth pattern
    exactly."""
    _require_cron_secret(authorization)
    classified_count = run_classification_batch(db)
    return {"status": "ok", "classified_count": classified_count}


@router.get("/api/cron/execute-deletions")
def execute_deletions_route(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict:
    """Spec 020's scheduled deletion job (contracts/api.md, research.md
    R1/R8) -- mirrors `reset_demo_data_route`'s auth pattern exactly.

    Runs the inactivity-warning reconciliation and deletion sweep
    (FR-011, FR-005) before draining up to `MAX_DELETIONS_PER_RUN`
    pending `DeletionRequest` rows, oldest first. Skips (never processes)
    a request whose target is somehow a demo account -- a defense-in-
    depth check alongside the submission-time guard in `deletion.py`
    (FR-007, research.md R7)."""
    _require_cron_secret(authorization)

    reconcile_inactivity_warnings(db)
    swept_count = sweep_inactive_accounts(db)

    pending = (
        db.query(DeletionRequest)
        .filter(DeletionRequest.completed_at.is_(None))
        .order_by(DeletionRequest.requested_at)
        .limit(MAX_DELETIONS_PER_RUN)
        .all()
    )
    processed_count = 0
    for deletion_request in pending:
        target_model = _DELETION_TARGET_MODEL[deletion_request.target_type]
        target = db.get(target_model, deletion_request.target_id)
        if target is not None and target.is_demo:
            # Should be unreachable -- submission time already blocks
            # demo targets (deletion.py) and is_demo is immutable -- but
            # if this defense-in-depth check ever does trigger, the
            # request otherwise sits `pending` forever with no visible
            # signal that something is stuck (PR #79 review).
            logger.warning(
                "deletion request %s skipped: target %s %s is a demo account",
                deletion_request.deletion_request_id,
                deletion_request.target_type,
                deletion_request.target_id,
            )
            continue
        try:
            execute_deletion(db, deletion_request)
        except Exception:
            # One request that reliably fails to execute (cascade gap,
            # transient DB error) must never block every other pending
            # deletion behind it in the queue -- roll back just this
            # request's partial work and keep going, same pattern as
            # run_classification_batch's per-pair isolation.
            db.rollback()
            logger.exception(
                "deletion execution failed for deletion_request=%s target_type=%s target_id=%s",
                deletion_request.deletion_request_id,
                deletion_request.target_type,
                deletion_request.target_id,
            )
            continue
        processed_count += 1

    remaining_pending_count = (
        db.query(DeletionRequest).filter(DeletionRequest.completed_at.is_(None)).count()
    )
    return {
        "status": "ok",
        "swept_count": swept_count,
        "processed_count": processed_count,
        "remaining_pending_count": remaining_pending_count,
    }
