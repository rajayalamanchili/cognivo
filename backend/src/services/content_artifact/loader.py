"""Loads a subject's content artifact (YAML) into Postgres.

Assigns `Topic.order_index` from the artifact's declaration order and
sets `Subject.validated_at` only after `validator.validate_content_artifact`
passes (FR-002) -- a subject failing validation MUST NOT become usable.
"""

import datetime
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.subject import Subject
from src.models.topic import Topic
from src.services.content_artifact.validator import (
    ValidatedContentArtifact,
    validate_content_artifact,
)


def load_content_artifact_file(path: str | Path) -> ValidatedContentArtifact:
    """Parse and validate a content artifact YAML file without touching the DB."""
    raw = yaml.safe_load(Path(path).read_text())
    return validate_content_artifact(raw)


def persist_content_artifact(db: Session, artifact: ValidatedContentArtifact) -> Subject:
    """Persist a validated content artifact, replacing any prior version.

    Idempotent: re-running against the same `subject_id` deletes the
    previous Subject/Topic/PrerequisiteEdge rows for that subject first
    (via cascade-free explicit delete, since GeneratedQuestion/
    MasteryState/AssessmentEvent rows referencing old topics must
    outlive a content-artifact reload) and reloads from the artifact.
    """
    existing = db.get(Subject, artifact.subject_id)
    if existing is not None:
        db.query(PrerequisiteEdge).filter(
            PrerequisiteEdge.subject_id == artifact.subject_id
        ).delete()
        db.query(Topic).filter(Topic.subject_id == artifact.subject_id).delete()
        db.delete(existing)
        db.flush()

    subject = Subject(
        subject_id=artifact.subject_id,
        display_name=artifact.display_name,
        content_version=artifact.content_version,
        validated_at=None,
    )
    db.add(subject)
    db.flush()

    for topic in artifact.topics:
        db.add(
            Topic(
                subject_id=artifact.subject_id,
                topic_id=topic.topic_id,
                display_name=topic.display_name,
                is_entry_level=topic.is_entry_level,
                skill_definition={
                    "skill": topic.skill_definition,
                    "difficulty_calibration": topic.difficulty_calibration,
                },
                order_index=topic.order_index,
            )
        )
    db.flush()

    for topic in artifact.topics:
        for prereq_id in topic.prerequisites:
            db.add(
                PrerequisiteEdge(
                    subject_id=artifact.subject_id,
                    from_topic_id=topic.topic_id,
                    to_topic_id=prereq_id,
                )
            )

    # Validation already passed by the time we got a ValidatedContentArtifact --
    # validated_at is set here, after all rows are staged, not before.
    subject.validated_at = datetime.datetime.now(datetime.UTC)
    db.commit()
    return subject


def load_content_artifact(db: Session, path: str | Path) -> Subject:
    artifact = load_content_artifact_file(path)
    return persist_content_artifact(db, artifact)
