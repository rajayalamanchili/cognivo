"""ComparisonReport aggregation types + JSON (de)serialization (data-model.md).

`ComparisonReport.to_dict()`/`from_dict()` match `contracts/api.md`'s
response schema exactly (minus the `published` wrapper key, which the
API route adds -- research.md §8), so the committed
`backend/evaluation/reports/latest.json` file and the API response stay
the same shape.
"""

import json
import random
import statistics
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from src.models.topic import Topic
from src.services.evaluation.conditions import (
    run_fixed_order_condition,
    run_random_condition,
    run_sequencing_condition,
)
from src.services.evaluation.profiles import SyntheticLearnerProfile, generate_population

Condition = Literal["sequencing", "random", "fixed_order"]


@dataclass(frozen=True)
class ConditionRunResult:
    """One (profile, subject, condition, learner) outcome (data-model.md)."""

    profile: str
    subject_id: str
    condition: Condition
    learner_index: int
    questions_to_mastery: int | None  # None if non-converged within budget
    converged: bool


@dataclass(frozen=True)
class ConditionStats:
    """Aggregated figures for one condition within one breakdown or the
    overall aggregate. `non_converged_rate` (`non_converged_count / n`)
    is computed and stored explicitly, not left for a report consumer to
    derive -- satisfies FR-006's "count/rate" wording literally (added
    post-`/speckit-analyze`, finding U1)."""

    mean: float
    median: float
    non_converged_count: int
    non_converged_rate: float
    n: int

    @classmethod
    def from_results(cls, results: list[ConditionRunResult]) -> "ConditionStats":
        """Mean/median are computed only over converged learners --
        non-convergers contribute to `non_converged_count`/`rate`, never
        silently dropped from `n` or allowed to skew the central figures
        (T029's edge case)."""
        n = len(results)
        converged_values = [result.questions_to_mastery for result in results if result.converged]
        non_converged_count = n - len(converged_values)
        return cls(
            mean=statistics.mean(converged_values) if converged_values else 0.0,
            median=statistics.median(converged_values) if converged_values else 0.0,
            non_converged_count=non_converged_count,
            non_converged_rate=(non_converged_count / n) if n else 0.0,
            n=n,
        )

    def to_dict(self) -> dict:
        return {
            "mean": self.mean,
            "median": self.median,
            "non_converged_count": self.non_converged_count,
            "non_converged_rate": self.non_converged_rate,
            "n": self.n,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConditionStats":
        return cls(
            mean=data["mean"],
            median=data["median"],
            non_converged_count=data["non_converged_count"],
            non_converged_rate=data["non_converged_rate"],
            n=data["n"],
        )


@dataclass(frozen=True)
class ProfileSubjectBreakdown:
    """One (profile, subject) entry in `ComparisonReport.breakdowns`."""

    profile: str
    subject_id: str
    conditions: dict[Condition, ConditionStats]

    def to_dict(self) -> dict:
        return {
            "profile": self.profile,
            "subject_id": self.subject_id,
            "conditions": {name: stats.to_dict() for name, stats in self.conditions.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileSubjectBreakdown":
        return cls(
            profile=data["profile"],
            subject_id=data["subject_id"],
            conditions={
                name: ConditionStats.from_dict(stats) for name, stats in data["conditions"].items()
            },
        )


@dataclass(frozen=True)
class ComparisonReport:
    """The self-describing Evaluation Run artifact (data-model.md) --
    everything `backend/evaluation/reports/latest.json` needs to answer
    "which run produced these numbers" (FR-013) without a separate log
    table."""

    run_timestamp: str
    seed: int
    profiles: list[str]
    subjects: list[str]
    population_size_per_profile: int
    max_questions_per_topic_budget: int
    breakdowns: list[ProfileSubjectBreakdown]
    aggregate: dict[Condition, ConditionStats]

    def to_dict(self) -> dict:
        return {
            "run_timestamp": self.run_timestamp,
            "seed": self.seed,
            "profiles": self.profiles,
            "subjects": self.subjects,
            "population_size_per_profile": self.population_size_per_profile,
            "max_questions_per_topic_budget": self.max_questions_per_topic_budget,
            "breakdowns": [breakdown.to_dict() for breakdown in self.breakdowns],
            "aggregate": {name: stats.to_dict() for name, stats in self.aggregate.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComparisonReport":
        return cls(
            run_timestamp=data["run_timestamp"],
            seed=data["seed"],
            profiles=data["profiles"],
            subjects=data["subjects"],
            population_size_per_profile=data["population_size_per_profile"],
            max_questions_per_topic_budget=data["max_questions_per_topic_budget"],
            breakdowns=[
                ProfileSubjectBreakdown.from_dict(breakdown) for breakdown in data["breakdowns"]
            ],
            aggregate={
                name: ConditionStats.from_dict(stats) for name, stats in data["aggregate"].items()
            },
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False)

    @classmethod
    def from_json(cls, raw: str) -> "ComparisonReport":
        return cls.from_dict(json.loads(raw))


def run_condition_results(
    db: Session,
    *,
    profile: SyntheticLearnerProfile,
    subject_id: str,
    topics: list[Topic],
    population_size: int,
    max_questions_per_topic: int,
    seed: int,
) -> list[ConditionRunResult]:
    """Runs all three ordering conditions (Sequencing Agent, random,
    fixed-order) for `population_size` simulated learners of `profile`
    against `subject_id`'s topics, and returns every learner's
    per-condition outcome. Every condition replays identical ground
    truth per learner (research.md §3) via one seeded population draw;
    a second, independent seeded RNG drives the conditions' own
    simulated-answer draws, consumed in a fixed (learner, condition)
    order so the whole run stays reproducible given `seed` (FR-007)."""
    learners = generate_population(profile, topics, population_size=population_size, seed=seed)
    sim_rng = random.Random(seed)

    results: list[ConditionRunResult] = []
    for learner in learners:
        sequencing_outcome = run_sequencing_condition(
            db,
            subject_id=subject_id,
            topics=topics,
            true_mastery=learner.true_mastery,
            max_questions_per_topic=max_questions_per_topic,
            rng=sim_rng,
        )
        random_outcome = run_random_condition(
            topics,
            true_mastery=learner.true_mastery,
            max_questions_per_topic=max_questions_per_topic,
            rng=sim_rng,
        )
        fixed_order_outcome = run_fixed_order_condition(
            topics,
            true_mastery=learner.true_mastery,
            max_questions_per_topic=max_questions_per_topic,
            rng=sim_rng,
        )

        for condition, outcome in (
            ("sequencing", sequencing_outcome),
            ("random", random_outcome),
            ("fixed_order", fixed_order_outcome),
        ):
            results.append(
                ConditionRunResult(
                    profile=profile.name,
                    subject_id=subject_id,
                    condition=condition,
                    learner_index=learner.learner_index,
                    questions_to_mastery=outcome.questions_to_mastery,
                    converged=outcome.converged,
                )
            )

    return results


def aggregate_stats(results: list[ConditionRunResult]) -> dict[Condition, ConditionStats]:
    """Groups a flat list of per-learner, per-condition results by
    `condition` and computes each condition's `ConditionStats`. Shared by
    `build_breakdown` (one profile/subject) and full-matrix orchestration
    pooling every breakdown's raw results into the report's `aggregate`."""
    by_condition: dict[Condition, list[ConditionRunResult]] = {}
    for result in results:
        by_condition.setdefault(result.condition, []).append(result)
    return {
        condition: ConditionStats.from_results(condition_results)
        for condition, condition_results in by_condition.items()
    }


def build_breakdown(
    profile: str, subject_id: str, results: list[ConditionRunResult]
) -> ProfileSubjectBreakdown:
    """Aggregates a flat list of per-learner, per-condition results (as
    produced by `run_condition_results`) into one `breakdowns` entry."""
    return ProfileSubjectBreakdown(
        profile=profile, subject_id=subject_id, conditions=aggregate_stats(results)
    )
