"""Integration test: an identical `--seed` produces a byte-identical
report (aside from `run_timestamp`) across two full-matrix runs (FR-007,
SC-003; quickstart.md step 4).

Writes to a `tmp_path`-scoped report file rather than the real
`backend/evaluation/reports/latest.json` -- this test must never clobber
a real published report.
"""

from src.services.evaluation import run_harness


def test_identical_seed_produces_reproducible_full_matrix_report(
    database_available, algebra_subject, biology_subject, tmp_path
):
    first = run_harness.main(["--seed", "1"], report_path=tmp_path / "run1.json")
    second = run_harness.main(["--seed", "1"], report_path=tmp_path / "run2.json")

    first_dict = first.to_dict()
    second_dict = second.to_dict()
    del first_dict["run_timestamp"]
    del second_dict["run_timestamp"]

    assert first_dict == second_dict
