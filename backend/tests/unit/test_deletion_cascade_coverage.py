"""Unit test wiring scripts/check_deletion_cascade_coverage.py into the
regular pytest suite (spec 020 SC-001), so it's an enforced CI gate on
every PR rather than a script someone has to remember to run by hand --
same pattern as tests/unit/test_no_subject_conditionals.py and
tests/unit/test_check_no_real_account_path.py.
"""

from scripts.check_deletion_cascade_coverage import find_violations


def test_every_fk_to_a_real_identity_table_is_cascade_covered():
    assert find_violations() == []
