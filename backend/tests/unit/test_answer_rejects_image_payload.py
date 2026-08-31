"""Unit test (FR-007): no image-upload answer path exists --
`validate_response_shape()` rejects a base64 data-URI string submitted
as a `numeric` or `multiple_choice` response exactly like any other
malformed answer, and a `free_text` response treats it as ordinary
text (no special image handling), mirroring
`test_grading_tolerance.py`'s pure-function convention.
"""

import pytest

from src.models.enums import QuestionType
from src.services.mastery.grading import validate_response_shape

_IMAGE_DATA_URI = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"


def test_numeric_rejects_image_data_uri():
    with pytest.raises(ValueError, match="numeric response must be a number"):
        validate_response_shape(QuestionType.NUMERIC, _IMAGE_DATA_URI)


def test_multiple_choice_rejects_image_data_uri():
    with pytest.raises(ValueError, match="multiple_choice response must be an integer"):
        validate_response_shape(QuestionType.MULTIPLE_CHOICE, _IMAGE_DATA_URI)


def test_free_text_accepts_image_data_uri_as_plain_string():
    # No special image-upload path exists (FR-007): a data-URI string is
    # just a string to free_text grading, not an image to be processed.
    validate_response_shape(QuestionType.FREE_TEXT, _IMAGE_DATA_URI)
