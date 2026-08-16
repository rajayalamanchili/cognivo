"""Unit test wiring scripts/check_no_subject_conditionals.py into the
regular pytest suite (SC-004), so it's an enforced CI gate on every PR
rather than a script someone has to remember to run by hand.
"""

from scripts.check_no_subject_conditionals import _known_subject_ids, find_violations


def test_no_engine_source_hardcodes_a_subject_id():
    subject_ids = _known_subject_ids()
    assert subject_ids, "expected >=1 content artifact under backend/content/*/subject.yaml"

    violations = find_violations(subject_ids)
    assert violations == [], "\n".join(violations)
