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
    """Persist a validated content artifact, upserting over any prior version.

    Idempotent: re-running against the same `subject_id` updates the
    Subject row and upserts each Topic row in place (same `topic_id`
    primary key) rather than deleting and recreating it, since
    GeneratedQuestion/MasteryState/AssessmentEvent rows referencing an
    existing topic must outlive a content-artifact reload -- a hard
    delete-then-reinsert breaks the moment any of those rows exist
    (`mastery_states_subject_id_topic_id_fkey`). Topics no longer listed
    in the artifact are deleted, matching the prior behavior for that
    (uncommon) case. PrerequisiteEdge rows are cheap to delete and
    recreate since nothing references them.
    """
    existing = db.get(Subject, artifact.subject_id)
    if existing is None:
        subject = Subject(
            subject_id=artifact.subject_id,
            display_name=artifact.display_name,
            content_version=artifact.content_version,
            validated_at=None,
        )
        db.add(subject)
        db.flush()
    else:
        subject = existing
        subject.display_name = artifact.display_name
        subject.content_version = artifact.content_version
        subject.validated_at = None

    db.query(PrerequisiteEdge).filter(PrerequisiteEdge.subject_id == artifact.subject_id).delete()

    existing_topics = {
        t.topic_id: t
        for t in db.query(Topic).filter(Topic.subject_id == artifact.subject_id)
    }
    artifact_topic_ids = {topic.topic_id for topic in artifact.topics}
    for topic_id, row in existing_topics.items():
        if topic_id not in artifact_topic_ids:
            db.delete(row)
    db.flush()

    for topic in artifact.topics:
        skill_definition = {
            "skill": topic.skill_definition,
            "difficulty_calibration": topic.difficulty_calibration,
        }
        row = existing_topics.get(topic.topic_id)
        if row is not None:
            row.display_name = topic.display_name
            row.is_entry_level = topic.is_entry_level
            row.skill_definition = skill_definition
            row.order_index = topic.order_index
        else:
            db.add(
                Topic(
                    subject_id=artifact.subject_id,
                    topic_id=topic.topic_id,
                    display_name=topic.display_name,
                    is_entry_level=topic.is_entry_level,
                    skill_definition=skill_definition,
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
