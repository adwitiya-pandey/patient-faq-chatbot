"""Tests for rate limiting, turn caps, and daily call cap (Step 5)."""

from datetime import date

from faq_bot.chat import handle_turn
from faq_bot.config import Config
from faq_bot.messages import DAILY_CAP_TEXT, RATE_LIMIT_TEXT
from faq_bot.rate_limit import RateLimiter
from tests.fakes import FakeLLM


def test_min_seconds_between_turns_with_fake_clock():
    """Verify turns spaced closer than min_seconds_between are rate limited."""
    current_time = [100.0]

    limiter = RateLimiter(time_fn=lambda: current_time[0])
    sess = "session-1"

    # Turn 1 at t=100.0 -> Allowed
    assert (
        limiter.check_turn_rate_limit(sess, max_turns=10, min_seconds_between=2.0)
        is None
    )

    # Turn 2 at t=101.0 (< 2.0s interval) -> Rate limited
    current_time[0] = 101.0
    assert (
        limiter.check_turn_rate_limit(sess, max_turns=10, min_seconds_between=2.0)
        == "rate_limited"
    )

    # Turn 3 at t=102.5 (>= 2.0s after Turn 1) -> Allowed
    current_time[0] = 102.5
    assert (
        limiter.check_turn_rate_limit(sess, max_turns=10, min_seconds_between=2.0)
        is None
    )


def test_max_turns_per_session():
    """Verify exceeding max_turns_per_session triggers rate_limited."""
    current_time = [0.0]
    limiter = RateLimiter(time_fn=lambda: current_time[0])
    sess = "session-capped"

    for _i in range(3):
        current_time[0] += 5.0
        assert (
            limiter.check_turn_rate_limit(sess, max_turns=3, min_seconds_between=1.0)
            is None
        )

    # 4th turn exceeds limit of 3
    current_time[0] += 5.0
    assert (
        limiter.check_turn_rate_limit(sess, max_turns=3, min_seconds_between=1.0)
        == "rate_limited"
    )


def test_daily_call_cap_and_midnight_utc_reset():
    """Verify daily call cap stops LLM calls and resets at midnight UTC."""
    today = [date(2026, 10, 27)]
    limiter = RateLimiter(date_fn=lambda: today[0])

    for _ in range(5):
        assert limiter.check_daily_cap(daily_cap=5) is None
        limiter.record_llm_call()

    # 6th call hits daily cap
    assert limiter.check_daily_cap(daily_cap=5) == "daily_cap_reached"

    # Advance date to next UTC day
    today[0] = date(2026, 10, 28)
    assert limiter.check_daily_cap(daily_cap=5) is None
    assert limiter.daily_calls == 0


def test_handle_turn_rate_limit_integration():
    """Verify handle_turn blocks fast turns without calling LLM and logs flag."""
    current_time = [10.0]
    limiter = RateLimiter(time_fn=lambda: current_time[0])
    fake_llm = FakeLLM(['{"category": "faq", "answer": "Visiting hours are 8am."}'])
    cfg = Config(gemini_api_key="test-key", min_seconds_between_turns=2.0)

    # First turn succeeds
    res1 = handle_turn(
        history=[],
        text="What are visiting hours?",
        llm=fake_llm,
        config=cfg,
        session_id="user-session-rl",
        rate_limiter=limiter,
    )
    assert res1.blocked is False
    assert len(fake_llm.calls) == 1

    # Second turn 0.5s later is rate limited
    current_time[0] = 10.5
    res2 = handle_turn(
        history=[],
        text="Where is the pharmacy?",
        llm=fake_llm,
        config=cfg,
        session_id="user-session-rl",
        rate_limiter=limiter,
    )
    assert res2.blocked is True
    assert res2.category == "rate_limited"
    assert res2.text == RATE_LIMIT_TEXT
    assert "rate_limited" in res2.guardrail_flags
    # Assert LLM was NOT called again
    assert len(fake_llm.calls) == 1


def test_handle_turn_daily_cap_integration():
    """Verify handle_turn blocks requests when daily cap is reached without calling LLM."""
    current_time = [100.0]
    limiter = RateLimiter(time_fn=lambda: current_time[0])
    # Exhaust daily cap
    for _ in range(3):
        limiter.record_llm_call()

    fake_llm = FakeLLM([])
    cfg = Config(
        gemini_api_key="test-key",
        daily_llm_call_cap=3,
        min_seconds_between_turns=0.1,
    )

    current_time[0] = 200.0
    res = handle_turn(
        history=[],
        text="Where is the pharmacy?",
        llm=fake_llm,
        config=cfg,
        session_id="new-session",
        rate_limiter=limiter,
    )

    assert res.blocked is True
    assert res.category == "daily_cap_reached"
    assert res.text == DAILY_CAP_TEXT
    assert "daily_cap_reached" in res.guardrail_flags
    assert len(fake_llm.calls) == 0
