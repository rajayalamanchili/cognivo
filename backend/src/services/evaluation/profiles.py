"""Synthetic learner profiles + seeded ground-truth generation (research.md §3, §10).

Ground truth is a per-(learner, topic) boolean latent state -- "truly
knows this topic" or not -- generated once per (profile, subject, seed)
and replayed identically across all three ordering conditions later
(`conditions.py`), which is what makes the conditions comparable at all
(research.md §3).
"""

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from src.models.topic import Topic

# (order_index, topic_count) -> (low, high) uniform range to draw a
# topic's true-mastery probability from (research.md §10).
ProbabilityRange = Callable[[int, int], tuple[float, float]]


@dataclass(frozen=True)
class SyntheticLearnerProfile:
    """A named archetype defining, per topic, the probability that this
    profile's learners truly know it (data-model.md's
    `SyntheticLearnerProfile`)."""

    name: str
    probability_range: ProbabilityRange


def _uniform_for_all(low: float, high: float) -> ProbabilityRange:
    return lambda order_index, topic_count: (low, high)


def _uneven_range(order_index: int, topic_count: int) -> tuple[float, float]:
    return (0.7, 0.9) if order_index % 2 == 0 else (0.05, 0.2)


def _prerequisite_bottleneck_range(order_index: int, topic_count: int) -> tuple[float, float]:
    return (0.05, 0.2) if order_index < topic_count / 2 else (0.6, 0.9)


COLD_START = SyntheticLearnerProfile("cold-start", _uniform_for_all(0.05, 0.25))
STRONG_PRIOR = SyntheticLearnerProfile("strong-prior", _uniform_for_all(0.6, 0.9))
UNEVEN = SyntheticLearnerProfile("uneven", _uneven_range)
PREREQUISITE_BOTTLENECK = SyntheticLearnerProfile(
    "prerequisite-bottleneck", _prerequisite_bottleneck_range
)

ALL_PROFILES: tuple[SyntheticLearnerProfile, ...] = (
    COLD_START,
    STRONG_PRIOR,
    UNEVEN,
    PREREQUISITE_BOTTLENECK,
)

PROFILES_BY_NAME: dict[str, SyntheticLearnerProfile] = {
    profile.name: profile for profile in ALL_PROFILES
}


@dataclass(frozen=True)
class SimulatedLearner:
    """One simulated learner's fixed ground truth (data-model.md's
    `SimulatedLearner`), reused identically across all three ordering
    conditions -- only the Sequencing Agent condition ever sets
    `demo_learner_id` (research.md §6)."""

    learner_index: int
    true_mastery: dict[str, bool]
    demo_learner_id: uuid.UUID | None = None


def generate_population(
    profile: SyntheticLearnerProfile,
    topics: list[Topic],
    *,
    population_size: int,
    seed: int,
) -> list[SimulatedLearner]:
    """Draws `population_size` simulated learners' ground truth for
    `profile` over `topics`, deterministic given `seed` (FR-007): the
    same seed always produces an identical per-learner true-mastery map.

    Each topic's true-mastery probability is drawn once (from the
    profile's range for that topic's position), then every learner's
    per-topic boolean is an independent Bernoulli draw of that fixed
    probability (research.md §3).
    """
    rng = random.Random(seed)
    ordered_topics = sorted(topics, key=lambda topic: topic.order_index)
    topic_count = len(ordered_topics)
    topic_probabilities = {
        topic.topic_id: rng.uniform(*profile.probability_range(topic.order_index, topic_count))
        for topic in ordered_topics
    }

    learners = []
    for learner_index in range(population_size):
        true_mastery = {
            topic_id: rng.random() < probability
            for topic_id, probability in topic_probabilities.items()
        }
        learners.append(SimulatedLearner(learner_index=learner_index, true_mastery=true_mastery))
    return learners
