"""Feature-scoped assertion that the evaluation harness introduces no
subject-id-keyed conditionals (Constitution Principle III; research.md
§11; quickstart.md step 10).

`tests/unit/test_no_subject_conditionals.py` already sweeps all of
`backend/src`, which includes `backend/src/services/evaluation/` -- this
test re-asserts the same gate scoped to this milestone for traceability.
"""

from scripts.check_no_subject_conditionals import _known_subject_ids, find_violations


def test_evaluation_harness_introduces_no_subject_conditionals():
    subject_ids = _known_subject_ids()
    assert subject_ids, "expected >=1 content artifact under backend/content/*/subject.yaml"

    violations = find_violations(subject_ids)
    assert violations == [], "\n".join(violations)
