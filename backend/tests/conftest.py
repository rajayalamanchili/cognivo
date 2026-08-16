"""Shared fixtures for tests that need a real Postgres database.

Integration and contract tests exercise the actual DB-backed API surface
(FR-013 -- no in-memory session state), so they need a real Postgres
instance, not a mock. They SKIP (not fail) when `DATABASE_URL` is unset
or unreachable, so the suite stays green in environments without a
provisioned database (e.g. a sandbox) while still running for real in
CI / any environment with one configured.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models.demo_learner_profile import DemoLearnerProfile
from src.services.content_artifact.loader import load_content_artifact


@pytest.fixture(scope="session")
def database_available() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set -- these tests require a real Postgres instance")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 -- any connectivity failure means skip
        pytest.skip(f"DATABASE_URL not reachable: {exc}")
    finally:
        engine.dispose()
    return database_url


@pytest.fixture()
def db_session(database_available: str):
    engine = create_engine(database_available)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def demo_learner(db_session) -> DemoLearnerProfile:
    learner = DemoLearnerProfile(display_name="Test Demo Learner", is_demo=True)
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)
    return learner


@pytest.fixture()
def algebra_subject(db_session):
    return load_content_artifact(db_session, "content/algebra-1/subject.yaml")


@pytest.fixture()
def biology_subject(db_session):
    return load_content_artifact(db_session, "content/biology/subject.yaml")
