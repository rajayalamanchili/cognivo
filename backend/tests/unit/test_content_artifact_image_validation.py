"""Unit tests: `load_content_artifact_file()`'s filesystem-level image
checks (FR-002, SC-003, spec.md Edge Cases). Pure filesystem tests
against a `tmp_path`-built content artifact -- no DB, mirroring
`test_quiz_difficulty.py`'s own pure-function convention. This
function never touches the database, so "no partial DB write" holds by
construction whenever it raises.
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
      summary: A topic used only to test image validation.
    image_asset:
      filename: {filename}
      alt_text: A description of the test image.
"""


def _write_artifact(tmp_path, filename: str) -> str:
    artifact_path = tmp_path / "subject.yaml"
    artifact_path.write_text(_SUBJECT_YAML_TEMPLATE.format(filename=filename))
    return str(artifact_path)


def test_missing_image_file_fails_validation(tmp_path):
    artifact_path = _write_artifact(tmp_path, "does-not-exist.png")

    with pytest.raises(ContentArtifactValidationError, match="does not exist"):
        load_content_artifact_file(artifact_path)


def test_oversized_image_file_fails_validation(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "too-big.png").write_bytes(b"0" * (1_048_576 + 1))
    artifact_path = _write_artifact(tmp_path, "too-big.png")

    with pytest.raises(ContentArtifactValidationError, match="exceeding"):
        load_content_artifact_file(artifact_path)


def test_wrong_format_image_file_fails_validation(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "diagram.gif").write_bytes(b"not a real gif, content doesn't matter here")
    artifact_path = _write_artifact(tmp_path, "diagram.gif")

    with pytest.raises(ContentArtifactValidationError, match="unsupported extension"):
        load_content_artifact_file(artifact_path)


def test_valid_image_file_passes_validation(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "diagram.png").write_bytes(b"a small valid-sized file")
    artifact_path = _write_artifact(tmp_path, "diagram.png")

    artifact = load_content_artifact_file(artifact_path)

    topic = artifact.topics[0]
    assert topic.image_asset == {
        "filename": "diagram.png",
        "alt_text": "A description of the test image.",
    }
