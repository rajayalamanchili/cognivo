import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Vercel's serverless Python Functions are stateless/ephemeral (FR-013,
# Constitution Principle IX) -- no long-lived in-process pool assumed to
# survive between invocations. `NullPool` would be the safer default for
# that model, but psycopg + SQLAlchemy's own pool is left as the
# per-function-instance default here since Neon's PgBouncer sits in
# front of it; revisit if cold-start connection overhead becomes a
# problem.
_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ["DATABASE_URL"]
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped Session."""
    session_local = get_sessionmaker()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
