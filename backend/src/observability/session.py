"""ADK session-state backend, Postgres-backed (FR-013, Constitution Principle IX).

Vercel's Python Functions are stateless/ephemeral between invocations --
no in-memory `InMemorySessionService` is usable here. ADK's
`DatabaseSessionService` persists agent session state (turns, tool
calls) to the same Postgres instance as everything else, so a session
survives across separate serverless invocations for the same
placement/question flow.

`DATABASE_URL` (backend/.env.example) uses the `postgresql+psycopg`
dialect, which SQLAlchemy 2.0's psycopg3 driver supports for both sync
(`create_engine`, used by `src/db.py`) and async (`create_async_engine`,
used internally by `DatabaseSessionService`) engines from the same URL --
no separate async connection string is needed.
"""

import os

from google.adk.sessions import DatabaseSessionService

_session_service: DatabaseSessionService | None = None


def get_database_session_service() -> DatabaseSessionService:
    """Returns a process-wide `DatabaseSessionService` singleton.

    Safe to call repeatedly within one Vercel Function invocation; a new
    instance (and thus a new async engine) is created fresh on cold
    start, per invocation, not shared across invocations.
    """
    global _session_service
    if _session_service is None:
        database_url = os.environ["DATABASE_URL"]
        _session_service = DatabaseSessionService(db_url=database_url)
    return _session_service
