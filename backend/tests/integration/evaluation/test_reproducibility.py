"""Integration test: an identical `--seed` produces a byte-identical
report (aside from `run_timestamp`) across two runs (FR-007, SC-003;
quickstart.md step 4 covers the full-matrix case manually).

Writes to a `tmp_path`-scoped report file rather than the real
`backend/evaluation/reports/latest.json` -- this test must never clobber
a real published report. Scoped to a single subject/profile pair with a
small `population_size` override (not the full profile x subject matrix
at research.md §10's full population of 30) -- SC-003 only requires
"same seed, same profile/subject configuration" reproduces identically;
the seeded-RNG mechanism that makes this true doesn't depend on how many
profile/subject combinations or how large a population it's exercised
over, and the Sequencing Agent condition's real-DB round-trips make a
full-scale x2 run prohibitively slow in CI/high-latency environments.
"""

from src.services.evaluation import run_harness

_SMALL_POPULATION_SIZE = 1


def test_identical_seed_produces_reproducible_report(
    database_available, algebra_subject, tmp_path
):
    argv = ["--subject", "algebra-1", "--profile", "strong-prior", "--seed", "1"]
    first = run_harness.main(
        argv, report_path=tmp_path / "run1.json", population_size=_SMALL_POPULATION_SIZE
    )
    second = run_harness.main(
        argv, report_path=tmp_path / "run2.json", population_size=_SMALL_POPULATION_SIZE
    )

    first_dict = first.to_dict()
    second_dict = second.to_dict()
    del first_dict["run_timestamp"]
    del second_dict["run_timestamp"]

    assert first_dict == second_dict
