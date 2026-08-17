"""ComparisonReport aggregation types + JSON (de)serialization (data-model.md).

`ComparisonReport.to_dict()`/`from_dict()` match `contracts/api.md`'s
response schema exactly (minus the `published` wrapper key, which the
API route adds -- research.md §8), so the committed
`backend/evaluation/reports/latest.json` file and the API response stay
the same shape.
"""

import json
import statistics
from dataclasses import dataclass
from typing import Literal

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
