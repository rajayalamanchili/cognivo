"""Vercel Python Function entrypoint (ASGI).

Vercel's Python runtime auto-detects an `app` variable in a file under
`api/` and serves it as a serverless function. `backend/src` uses
`from src...` imports throughout (matching `backend/scripts/*.py`'s own
`sys.path` convention) rather than a src-layout package install, so the
same `backend/` root must be on `sys.path` here too.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.main import app  # noqa: E402

__all__ = ["app"]
