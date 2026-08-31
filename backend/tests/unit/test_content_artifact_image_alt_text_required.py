"""Unit test: a content artifact whose `image_asset` entry omits (or
blanks) `alt_text` fails validation with `ContentArtifactValidationError`
(FR-003, SC-002, spec.md US3).

Pure validation test, no DB -- `validate_content_artifact()` (called by
`load_content_artifact_file()` before any filesystem/DB access for the
image) raises before `persist_content_artifact()` is ever reached, so
`Subject.validated_at` is never set by construction, mirroring
`test_content_artifact_image_validation.py`'s own "no partial DB write"
convention (T011).
"""

import pytest

from src.services.content_artifact.loader import load_content_artifact_file
from src.services.content_artifact.validator import ContentArtifactValidationError

_SUBJECT_YAML_TEMPLATE = """\
subject_id: test-subject
display_name: Test Subject
content_version: "1.0.0"
topics:
  - topic_id: topic-with-image
    display_name: Topic With Image
    skill_definition:
      summary: A topic used only to test image alt-text validation.
    image_asset:
      filename: diagram.png
{alt_text_line}
"""


def _write_artifact(tmp_path, alt_text_line: str) -> str:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "diagram.png").write_bytes(b"a small valid-sized file")
    artifact_path = tmp_path / "subject.yaml"
    artifact_path.write_text(_SUBJECT_YAML_TEMPLATE.format(alt_text_line=alt_text_line))
    return str(artifact_path)


def test_missing_alt_text_fails_validation(tmp_path):
    artifact_path = _write_artifact(tmp_path, alt_text_line="")

    with pytest.raises(ContentArtifactValidationError, match="alt_text"):
        load_content_artifact_file(artifact_path)


def test_blank_alt_text_fails_validation(tmp_path):
    artifact_path = _write_artifact(tmp_path, alt_text_line="      alt_text: '   '")

    with pytest.raises(ContentArtifactValidationError, match="alt_text"):
        load_content_artifact_file(artifact_path)
