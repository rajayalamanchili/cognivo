"""Public URL convention for a topic's bundled image asset (FR-005,
research.md §1/§5). Defined once, here, so `agents/sequencing/agent.py`
and `services/quiz/session.py` never each invent their own string.
"""


def content_image_url(subject_id: str, filename: str) -> str:
    """The Next.js-served static URL for a subject's image file, synced
    at build time from `backend/content/<subject_id>/images/<filename>`
    into `frontend/public/content-images/<subject_id>/<filename>`."""
    return f"/content-images/{subject_id}/{filename}"
