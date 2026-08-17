"""Unit test wiring
scripts/check_no_shared_recommendation_sequencing_fixtures.py into the
regular pytest suite (SC-005), so it's an enforced CI gate on every PR
rather than a script someone has to remember to run by hand.
"""

from scripts.check_no_shared_recommendation_sequencing_fixtures import find_violations


def test_no_shared_fixtures_between_recommendation_and_sequencing_tests():
    violations = find_violations()
    assert violations == [], "\n".join(violations)
