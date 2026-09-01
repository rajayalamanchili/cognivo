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
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from scripts.reset_demo_data import reset_demo_data
from src.db import get_db
from src.services.misconception.classify import run_classification_batch

router = APIRouter()


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
