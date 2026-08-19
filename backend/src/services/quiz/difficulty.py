"""Streak-based in-quiz difficulty adjustment (FR-002, FR-007,
research.md §1).

`next_difficulty` is the pure single-step rule, directly unit-testable
with no DB -- mirrors `weak_area.py`'s/`next_step.py`'s/
`agents/sequencing/agent.py`'s own pure-rule-plus-DB-orchestration
split. `current_difficulty_for_topic` replays a topic's full in-quiz
answer history through it rather than persisting a mutable
band/streak column anywhere, so there is exactly one source of truth
(the answer history itself, research.md §1).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from src.models.enums import DifficultyBand

_BAND_ORDER = [DifficultyBand.EASY, DifficultyBand.MEDIUM, DifficultyBand.HARD]


@dataclass(frozen=True)
class DifficultyStep:
    band: DifficultyBand
    streak: int
    streak_length_at_decision: int
    held_at_bound: bool


def next_difficulty(band: DifficultyBand, streak: int, *, correct: bool) -> DifficultyStep:
    """One streak-based step. `streak` is signed: positive = consecutive
    correct, negative = consecutive incorrect, 0 = neutral (the
    caller's post-reset state from the previous step). Two consecutive
    same-direction answers move exactly one band; holding at a bound
    (FR-007) still resets the streak to zero, since the two-answer
    attempt has been resolved either way, not left pinned at the
    threshold (Clarifications/checklist review, 2026-08-18)."""
    if correct:
        streak = streak + 1 if streak >= 0 else 1
    else:
        streak = streak - 1 if streak <= 0 else -1

    streak_length_at_decision = abs(streak)
    held_at_bound = False

    if streak >= 2:
        index = _BAND_ORDER.index(band)
        if index + 1 < len(_BAND_ORDER):
            band = _BAND_ORDER[index + 1]
        else:
            held_at_bound = True
        streak = 0
    elif streak <= -2:
        index = _BAND_ORDER.index(band)
        if index - 1 >= 0:
            band = _BAND_ORDER[index - 1]
        else:
            held_at_bound = True
        streak = 0

    return DifficultyStep(
        band=band,
        streak=streak,
        streak_length_at_decision=streak_length_at_decision,
        held_at_bound=held_at_bound,
    )


def replay_topic_state(history: Sequence[bool]) -> tuple[DifficultyBand, int]:
    """The (band, streak) state after replaying a topic's ordered
    (correct/incorrect) in-quiz answer history from the start (`easy`,
    streak 0) -- the full state `next_difficulty` needs as input to
    compute the *next* step, e.g. to log the decision a not-yet-recorded
    answer would produce."""
    band = DifficultyBand.EASY
    streak = 0
    for correct in history:
        step = next_difficulty(band, streak, correct=correct)
        band, streak = step.band, step.streak
    return band, streak


def current_difficulty_for_topic(history: Sequence[bool]) -> DifficultyBand:
    """The topic's current in-quiz difficulty band, replayed from its
    ordered (correct/incorrect) answer history starting at `easy` with
    a zero streak (FR-002's "first question is always easy")."""
    band, _streak = replay_topic_state(history)
    return band
