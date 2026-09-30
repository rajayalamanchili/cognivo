"""Unit test: `compute_hit_rates()`'s per-cache-type aggregation (spec
015 User Story 3, SC-001's per-type scoping, Clarifications 2026-09-02).

Pure function, no DB -- `AssessmentEvent` rows are built in memory, never
persisted (mirrors `batch_eval_questions.py`'s pure `evaluate_sample()`).

`compute_shielding_hit_rate()` (spec 026 User Story 3) is the shielding
counterpart -- summed over `TutorExchange.shielding_checks_total`/
`shielding_checks_from_cache`, a per-check (not per-exchange) rate,
since one exchange can span several independent checks with mixed
hit/miss outcomes (data-model.md §3).
"""

from scripts.cache_hit_rate_report import compute_hit_rates, compute_shielding_hit_rate
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.tutor_exchange import TutorExchange


def _event(event_type: AssessmentEventType, payload: dict) -> AssessmentEvent:
    return AssessmentEvent(
        learner_id=None,
        event_type=event_type,
        subject_id="algebra-1",
        topic_id="integers-and-operations",
        payload=payload,
    )


def test_hit_rates_are_scoped_independently_per_cache_type():
    events = [
        # question-generation: 2 hits, 1 miss -> 66.7%
        _event(AssessmentEventType.NEXT_TOPIC_SELECTED, {"served_from_cache": True}),
        _event(AssessmentEventType.NEXT_TOPIC_SELECTED, {"served_from_cache": True}),
        _event(
            AssessmentEventType.NEXT_TOPIC_SELECTED,
            {"served_from_cache": False, "cache_miss_reason": "no_matching_entry"},
        ),
        # grading: 1 hit, 3 misses -> 25%
        _event(AssessmentEventType.ANSWER_SUBMITTED, {"served_from_cache": True}),
        _event(
            AssessmentEventType.ANSWER_SUBMITTED,
            {"served_from_cache": False, "cache_miss_reason": "no_matching_entry"},
        ),
        _event(
            AssessmentEventType.ANSWER_SUBMITTED,
            {"served_from_cache": False, "cache_miss_reason": "no_matching_entry"},
        ),
        _event(
            AssessmentEventType.ANSWER_SUBMITTED,
            {"served_from_cache": False, "cache_miss_reason": "storage_failure"},
        ),
        # structured (MC/numeric) answers carry no served_from_cache key
        # at all -- never counted as cache-eligible either way
        _event(AssessmentEventType.ANSWER_SUBMITTED, {"correct": True}),
        # a non-cache-related event type is ignored entirely
        _event(AssessmentEventType.MASTERY_UPDATED, {"served_from_cache": True}),
    ]

    stats = compute_hit_rates(events)

    assert stats["question_generation"].hits == 2
    assert stats["question_generation"].total == 3
    assert round(stats["question_generation"].hit_rate_percent, 1) == 66.7

    assert stats["grading"].hits == 1
    assert stats["grading"].total == 4
    assert stats["grading"].hit_rate_percent == 25.0
    assert stats["grading"].miss_reasons == {"no_matching_entry": 2, "storage_failure": 1}


def test_no_cache_eligible_events_returns_empty_stats():
    events = [_event(AssessmentEventType.MASTERY_UPDATED, {"answer_correct": True})]
    assert compute_hit_rates(events) == {}


def test_moderation_hit_rate_scoped_independently_across_both_event_types():
    events = [
        # moderation-allow path (ANSWER_SUBMITTED): 1 hit, 1 miss
        _event(
            AssessmentEventType.ANSWER_SUBMITTED,
            {"served_from_cache": True, "moderation_served_from_cache": True},
        ),
        _event(
            AssessmentEventType.ANSWER_SUBMITTED,
            {
                "served_from_cache": False,
                "cache_miss_reason": "no_matching_entry",
                "moderation_served_from_cache": False,
                "moderation_cache_miss_reason": "no_matching_entry",
            },
        ),
        # moderation-block path (FREE_TEXT_SUBMISSION_REJECTED): 1 hit
        _event(
            AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
            {"reason": "moderation", "moderation_served_from_cache": True},
        ),
        # rejected for a non-moderation reason -- no moderation keys at all
        _event(AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED, {"reason": "too_long"}),
    ]

    stats = compute_hit_rates(events)

    assert stats["moderation"].hits == 2
    assert stats["moderation"].total == 3
    assert stats["moderation"].miss_reasons == {"no_matching_entry": 1}
    # grading's own rate (from the same ANSWER_SUBMITTED rows) is untouched
    assert stats["grading"].hits == 1
    assert stats["grading"].total == 2


def _exchange(total: int, from_cache: int) -> TutorExchange:
    return TutorExchange(
        question_text="q",
        shielding_checks_total=total,
        shielding_checks_from_cache=from_cache,
    )


def test_shielding_hit_rate_is_summed_over_checks_not_averaged_per_exchange():
    exchanges = [
        _exchange(total=2, from_cache=2),  # both checks hit
        _exchange(total=3, from_cache=0),  # none hit
        _exchange(total=0, from_cache=0),  # no open questions, no checks at all
    ]

    stats = compute_shielding_hit_rate(exchanges)

    assert stats.total == 5
    assert stats.hits == 2
    assert stats.hit_rate_percent == 40.0
