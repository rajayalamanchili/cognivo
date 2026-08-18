"""Unit test: ground-truth generation is deterministic given a fixed
seed (FR-007; validates T003 -- profiles.py)."""

from src.models.topic import Topic
from src.services.evaluation.profiles import ALL_PROFILES, generate_population


def _topics(count: int = 8) -> list[Topic]:
    return [
        Topic(
            subject_id="fake-subject",
            topic_id=f"topic-{i}",
            display_name=f"Topic {i}",
            is_entry_level=(i == 0),
            skill_definition={},
            order_index=i,
        )
        for i in range(count)
    ]


def test_same_seed_produces_identical_population():
    topics = _topics()
    for profile in ALL_PROFILES:
        first = generate_population(profile, topics, population_size=30, seed=42)
        second = generate_population(profile, topics, population_size=30, seed=42)
        assert first == second


def test_different_seed_produces_different_population():
    topics = _topics()
    profile = ALL_PROFILES[0]
    first = generate_population(profile, topics, population_size=30, seed=1)
    second = generate_population(profile, topics, population_size=30, seed=2)
    assert first != second


def test_topic_order_in_input_list_does_not_affect_result():
    # generate_population sorts by order_index internally -- the caller's
    # query-result ordering must not silently change the ground truth.
    topics = _topics()
    shuffled = list(reversed(topics))
    profile = ALL_PROFILES[2]  # "uneven" -- order-index-parity-sensitive
    ordered_result = generate_population(profile, topics, population_size=10, seed=7)
    shuffled_result = generate_population(profile, shuffled, population_size=10, seed=7)
    assert ordered_result == shuffled_result


def test_population_size_matches_requested_count():
    topics = _topics()
    population = generate_population(ALL_PROFILES[0], topics, population_size=17, seed=1)
    assert len(population) == 17
    assert [learner.learner_index for learner in population] == list(range(17))


def test_every_topic_has_a_ground_truth_entry():
    topics = _topics()
    population = generate_population(ALL_PROFILES[0], topics, population_size=5, seed=1)
    expected_topic_ids = {topic.topic_id for topic in topics}
    for learner in population:
        assert set(learner.true_mastery.keys()) == expected_topic_ids
