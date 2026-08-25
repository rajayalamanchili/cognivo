"""Loads a subject's content artifact (YAML) into Postgres.

Assigns `Topic.order_index` from the artifact's declaration order and
sets `Subject.validated_at` only after `validator.validate_content_artifact`
passes (FR-002) -- a subject failing validation MUST NOT become usable.
"""

import datetime
import os
from pathlib import Path

import litellm
import yaml
from sqlalchemy.orm import Session

from src.models.content_passage_embedding import ContentPassageEmbedding
from src.models.enums import PassageField
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.subject import Subject
from src.models.topic import Topic
from src.services.content_artifact.validator import (
    ValidatedContentArtifact,
    ValidatedTopic,
    validate_content_artifact,
)

# research.md §5: one passage per topic's skill_definition.summary, plus
# each present difficulty_calibration band -- up to four passages per
# topic, in a fixed, deterministic order.
_DIFFICULTY_BAND_FIELDS = (
    ("easy", PassageField.DIFFICULTY_EASY),
    ("medium", PassageField.DIFFICULTY_MEDIUM),
    ("hard", PassageField.DIFFICULTY_HARD),
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
        t.topic_id: t for t in db.query(Topic).filter(Topic.subject_id == artifact.subject_id)
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


def _passage_texts(topic: ValidatedTopic) -> list[tuple[PassageField, str]]:
    """The (field, text) pairs to embed for one topic, sourced directly
    from the already-validated `ValidatedTopic` -- not re-derived from
    `Topic.skill_definition`'s persisted JSON shape, which nests
    `difficulty_calibration` under a different key structure
    (data-model.md's `content_passage_embeddings` section)."""
    passages: list[tuple[PassageField, str]] = []
    summary = topic.skill_definition.get("summary")
    if summary:
        passages.append((PassageField.SKILL_SUMMARY, summary))
    for band, field in _DIFFICULTY_BAND_FIELDS:
        text = topic.difficulty_calibration.get(band)
        if text:
            passages.append((field, text))
    return passages


def generate_passage_embeddings(db: Session, artifact: ValidatedContentArtifact) -> None:
    """Regenerate this subject's `ContentPassageEmbedding` rows for the
    Tutor Agent's `pgvector` retrieval (spec 012 research.md §5), via
    `litellm.embedding()` against `TUTOR_EMBEDDING_MODEL` (default
    Voyage `voyage-3`).

    Upserts in place keyed by `(subject_id, topic_id, field)` rather
    than deleting and reinserting -- the same upsert-not-accumulate
    discipline `persist_content_artifact` already applies to Topic rows
    above -- so a reload under an unchanged `content_version` is a
    no-op-shaped update, and a version bump simply rewrites `text`/
    `embedding`/`content_version` on the existing row. A topic or
    difficulty band no longer present in `artifact` has its row deleted
    outright (data-model.md: a superseded-version row must never be
    left for retrieval to serve stale text).
    """
    passages_by_topic: dict[str, list[tuple[PassageField, str]]] = {
        topic.topic_id: _passage_texts(topic) for topic in artifact.topics
    }
    all_texts = [text for passages in passages_by_topic.values() for _, text in passages]

    existing = {
        (row.topic_id, row.field): row
        for row in db.query(ContentPassageEmbedding).filter(
            ContentPassageEmbedding.subject_id == artifact.subject_id
        )
    }

    if not all_texts:
        for row in existing.values():
            db.delete(row)
        db.commit()
        return

    model_name = os.environ.get("TUTOR_EMBEDDING_MODEL", "voyage/voyage-3")
    response = litellm.embedding(model=model_name, input=all_texts)
    embeddings = iter(item["embedding"] for item in response.data)

    seen_keys: set[tuple[str, PassageField]] = set()
    for topic_id, passages in passages_by_topic.items():
        for field, text in passages:
            embedding = next(embeddings)
            key = (topic_id, field)
            seen_keys.add(key)
            row = existing.get(key)
            if row is not None:
                row.text = text
                row.embedding = embedding
                row.content_version = artifact.content_version
            else:
                db.add(
                    ContentPassageEmbedding(
                        subject_id=artifact.subject_id,
                        topic_id=topic_id,
                        field=field,
                        text=text,
                        embedding=embedding,
                        content_version=artifact.content_version,
                    )
                )

    for key, row in existing.items():
        if key not in seen_keys:
            db.delete(row)

    db.commit()


def load_content_artifact(db: Session, path: str | Path) -> Subject:
    """Validate and persist a content artifact -- topic graph only, no
    embedding generation (see `generate_passage_embeddings` above).

    Deliberately NOT wired together with `generate_passage_embeddings`
    here: this function is the shared fixture/helper dozens of existing
    tests across every prior milestone already call to get a persisted
    Subject, and coupling it to a live Voyage API call would make their
    setup depend on `VOYAGE_API_KEY`/network access that has nothing to
    do with what they're testing -- a regression `/speckit-implement`'s
    Phase 6 SC-005 check (Milestones 1-8 unmodified) would catch.
    `scripts/load_content_artifact.py` -- the actual operational
    load pipeline a human runs (quickstart.md) -- calls both in
    sequence; call `generate_passage_embeddings` directly wherever a
    test specifically needs real retrieval passages.
    """
    artifact = load_content_artifact_file(path)
    return persist_content_artifact(db, artifact)
