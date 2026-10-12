"""Unit tests: `backend/src/api/routes/auth.py`'s `_pad_to_floor` --
the constant-time mitigation for forgot-password's account-enumeration
timing oracle (SC-003). Mocks `time.sleep` so this is deterministic,
not a real-wall-clock-timing assertion (which would be flaky in CI).
"""

from unittest.mock import patch

from src.api.routes import auth


def test_pads_up_to_the_floor_when_work_was_fast(monkeypatch):
    monkeypatch.setattr(auth, "_FORGOT_PASSWORD_RESPONSE_FLOOR_SECONDS", 2.0)
    with patch.object(auth.time, "monotonic", return_value=100.1):
        with patch.object(auth.time, "sleep") as mock_sleep:
            auth._pad_to_floor(100.0)
    mock_sleep.assert_called_once()
    (slept,) = mock_sleep.call_args.args
    assert 1.8 < slept <= 1.901


def test_does_not_sleep_when_work_already_exceeded_the_floor(monkeypatch):
    monkeypatch.setattr(auth, "_FORGOT_PASSWORD_RESPONSE_FLOOR_SECONDS", 2.0)
    with patch.object(auth.time, "monotonic", return_value=103.0):
        with patch.object(auth.time, "sleep") as mock_sleep:
            auth._pad_to_floor(100.0)
    mock_sleep.assert_not_called()
