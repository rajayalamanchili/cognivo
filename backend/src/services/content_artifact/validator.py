"""Load-time content-artifact schema + graph-integrity validation (FR-002).

A subject's content artifact is a YAML file describing its topic graph.
This module never touches the database or the filesystem -- it takes an
already-parsed artifact dict and either returns a normalized structure
or raises `ContentArtifactValidationError`. The loader
(`services/content_artifact/loader.py`) is the only caller that persists
the result, and it MUST NOT set `Subject.validated_at` unless this
validator has run without raising.
"""

from dataclasses import dataclass


class ContentArtifactValidationError(Exception):
    """Raised when a content artifact fails schema or graph validation."""


@dataclass(frozen=True)
class ValidatedTopic:
    topic_id: str
    display_name: str
    skill_definition: dict
    prerequisites: tuple[str, ...]
    is_entry_level: bool
    order_index: int
    difficulty_calibration: dict
    image_asset: dict | None
    misconceptions: tuple[dict, ...]


@dataclass(frozen=True)
class ValidatedContentArtifact:
    subject_id: str
    display_name: str
    content_version: str
    topics: tuple[ValidatedTopic, ...]


_REQUIRED_SUBJECT_FIELDS = ("subject_id", "display_name", "content_version", "topics")
_REQUIRED_TOPIC_FIELDS = ("topic_id", "display_name", "skill_definition")
_VALID_DIFFICULTY_BANDS = ("easy", "medium", "hard")


def validate_content_artifact(raw: dict) -> ValidatedContentArtifact:
    """Validate a parsed content-artifact dict.

    Checks, in order: required top-level fields present; `topics` is a
    non-empty list; every topic has its required fields; `topic_id`
    values are unique within the subject; every `prerequisites` entry
    references a `topic_id` defined in the same artifact; the resulting
    prerequisite graph is acyclic (which, combined with the previous
    check, guarantees every topic is reachable from some entry-level
    topic -- a finite acyclic graph always has at least one zero-
    prerequisite node).

    Raises `ContentArtifactValidationError` on any failure. Returns a
    normalized, order-preserving `ValidatedContentArtifact` on success.
    """
    _require_fields(raw, _REQUIRED_SUBJECT_FIELDS, context="content artifact")

    subject_id = raw["subject_id"]
    raw_topics = raw["topics"]
    if not isinstance(raw_topics, list) or len(raw_topics) == 0:
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': 'topics' must be a non-empty list"
        )

    topic_ids: list[str] = []
    prereqs_by_topic: dict[str, tuple[str, ...]] = {}
    normalized_by_topic: dict[str, dict] = {}

    for index, raw_topic in enumerate(raw_topics):
        _require_fields(
            raw_topic,
            _REQUIRED_TOPIC_FIELDS,
            context=f"subject '{subject_id}', topic index {index}",
        )
        topic_id = raw_topic["topic_id"]
        if topic_id in normalized_by_topic:
            raise ContentArtifactValidationError(
                f"subject '{subject_id}': duplicate topic_id '{topic_id}'"
            )
        prerequisites = tuple(raw_topic.get("prerequisites") or [])
        difficulty_calibration = raw_topic.get("difficulty_calibration") or {}
        _validate_difficulty_calibration(subject_id, topic_id, difficulty_calibration)
        image_asset = raw_topic.get("image_asset")
        _validate_image_asset(subject_id, topic_id, image_asset)
        misconceptions = _validate_misconceptions(
            subject_id, topic_id, raw_topic.get("misconceptions")
        )

        topic_ids.append(topic_id)
        prereqs_by_topic[topic_id] = prerequisites
        normalized_by_topic[topic_id] = {
            "topic_id": topic_id,
            "display_name": raw_topic["display_name"],
            "skill_definition": raw_topic["skill_definition"],
            "prerequisites": prerequisites,
            "order_index": index,
            "difficulty_calibration": difficulty_calibration,
            "image_asset": image_asset,
            "misconceptions": misconceptions,
        }

    topic_id_set = set(topic_ids)
    for topic_id, prerequisites in prereqs_by_topic.items():
        for prereq_id in prerequisites:
            if prereq_id not in topic_id_set:
                raise ContentArtifactValidationError(
                    f"subject '{subject_id}': topic '{topic_id}' lists undefined "
                    f"prerequisite '{prereq_id}'"
                )
            if prereq_id == topic_id:
                raise ContentArtifactValidationError(
                    f"subject '{subject_id}': topic '{topic_id}' lists itself as a prerequisite"
                )

    _check_acyclic(subject_id, prereqs_by_topic)

    validated_topics = tuple(
        ValidatedTopic(
            topic_id=t["topic_id"],
            display_name=t["display_name"],
            skill_definition=t["skill_definition"],
            prerequisites=t["prerequisites"],
            is_entry_level=len(t["prerequisites"]) == 0,
            order_index=t["order_index"],
            difficulty_calibration=t["difficulty_calibration"],
            image_asset=t["image_asset"],
            misconceptions=t["misconceptions"],
        )
        for t in normalized_by_topic.values()
    )

    return ValidatedContentArtifact(
        subject_id=subject_id,
        display_name=raw["display_name"],
        content_version=str(raw["content_version"]),
        topics=validated_topics,
    )


def _require_fields(obj: dict, fields: tuple[str, ...], *, context: str) -> None:
    if not isinstance(obj, dict):
        raise ContentArtifactValidationError(f"{context}: expected a mapping, got {type(obj)}")
    missing = [f for f in fields if f not in obj]
    if missing:
        raise ContentArtifactValidationError(f"{context}: missing required field(s) {missing}")


def _validate_difficulty_calibration(subject_id: str, topic_id: str, calibration: dict) -> None:
    if not isinstance(calibration, dict):
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' difficulty_calibration must be a mapping"
        )
    unknown_bands = set(calibration) - set(_VALID_DIFFICULTY_BANDS)
    if unknown_bands:
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' has unknown difficulty band(s) "
            f"{sorted(unknown_bands)}; must be a subset of {_VALID_DIFFICULTY_BANDS}"
        )


def _validate_image_asset(subject_id: str, topic_id: str, image_asset: object) -> None:
    """Schema-only check for an optional per-topic `image_asset` (FR-001/
    FR-003) -- no filesystem access here; missing-file/oversized/wrong-
    format checks are filesystem-touching and live in
    `services/content_artifact/loader.py` instead (data-model.md)."""
    if image_asset is None:
        return
    if not isinstance(image_asset, dict):
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' image_asset must be a mapping"
        )
    filename = image_asset.get("filename")
    if not isinstance(filename, str) or not filename:
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' image_asset.filename "
            "must be a non-empty string"
        )
    alt_text = image_asset.get("alt_text")
    if not isinstance(alt_text, str) or not alt_text.strip():
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' image_asset.alt_text "
            "must be a non-empty string (FR-003)"
        )


def _validate_misconceptions(
    subject_id: str, topic_id: str, misconceptions: object
) -> tuple[dict, ...]:
    """Schema-only check for an optional per-topic `misconceptions` list
    (spec 013 FR-002) -- a subject/topic defining none is valid (spec
    013's edge case); Principle III requires this taxonomy live here,
    in the content artifact, never as an engine-level hardcoded list."""
    if misconceptions is None:
        return ()
    if not isinstance(misconceptions, list):
        raise ContentArtifactValidationError(
            f"subject '{subject_id}': topic '{topic_id}' misconceptions must be a list"
        )
    seen_ids: set[str] = set()
    validated: list[dict] = []
    for entry in misconceptions:
        if not isinstance(entry, dict):
            raise ContentArtifactValidationError(
                f"subject '{subject_id}': topic '{topic_id}' misconceptions entries "
                "must be mappings"
            )
        misconception_id = entry.get("misconception_id")
        if not isinstance(misconception_id, str) or not misconception_id:
            raise ContentArtifactValidationError(
                f"subject '{subject_id}': topic '{topic_id}' misconceptions entry "
                "missing a non-empty 'misconception_id'"
            )
        if misconception_id in seen_ids:
            raise ContentArtifactValidationError(
                f"subject '{subject_id}': topic '{topic_id}' duplicate "
                f"misconception_id '{misconception_id}'"
            )
        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ContentArtifactValidationError(
                f"subject '{subject_id}': topic '{topic_id}' misconception "
                f"'{misconception_id}' missing a non-empty 'description'"
            )
        seen_ids.add(misconception_id)
        validated.append({"misconception_id": misconception_id, "description": description})
    return tuple(validated)


def _check_acyclic(subject_id: str, prereqs_by_topic: dict[str, tuple[str, ...]]) -> None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {topic_id: WHITE for topic_id in prereqs_by_topic}

    def visit(topic_id: str, path: list[str]) -> None:
        color[topic_id] = GRAY
        path.append(topic_id)
        for prereq_id in prereqs_by_topic[topic_id]:
            if color[prereq_id] == GRAY:
                cycle = path[path.index(prereq_id) :] + [prereq_id]
                raise ContentArtifactValidationError(
                    f"subject '{subject_id}': prerequisite cycle detected: {' -> '.join(cycle)}"
                )
            if color[prereq_id] == WHITE:
                visit(prereq_id, path)
        path.pop()
        color[topic_id] = BLACK

    for topic_id in prereqs_by_topic:
        if color[topic_id] == WHITE:
            visit(topic_id, [])
