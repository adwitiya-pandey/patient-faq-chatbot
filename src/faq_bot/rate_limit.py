"""Rate limiting, session turn caps, and daily process-wide call counters."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass
class SessionState:
    """Track turn count and timing for an active user session."""

    turn_count: int = 0
    last_turn_time: float = 0.0


class RateLimiter:
    """In-memory rate limiter and daily cap tracker.

    Manages:
    1. Maximum turns per session (MAX_TURNS_PER_SESSION)
    2. Minimum interval between turns per session (MIN_SECONDS_BETWEEN_TURNS)
    3. Process-wide daily LLM call cap reset at UTC midnight (DAILY_LLM_CALL_CAP)
    """

    def __init__(
        self,
        time_fn: Callable[[], float] | None = None,
        date_fn: Callable[[], date] | None = None,
    ) -> None:
        self._time_fn = time_fn or time.time
        self._date_fn = date_fn or (lambda: datetime.now(UTC).date())
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionState] = {}
        self._daily_calls: int = 0
        self._current_date: date = self._date_fn()

    def reset(self) -> None:
        """Reset internal session and counter state (primarily for tests)."""
        with self._lock:
            self._sessions.clear()
            self._daily_calls = 0
            self._current_date = self._date_fn()

    def check_turn_rate_limit(
        self,
        session_id: str,
        max_turns: int = 30,
        min_seconds_between: float = 2.0,
    ) -> str | None:
        """Check if current turn violates session turn cap or inter-turn interval.

        Returns:
            'rate_limited' if limits are exceeded, None if permitted.
        """
        now = self._time_fn()
        with self._lock:
            state = self._sessions.setdefault(session_id, SessionState())
            # Check maximum turns per session
            if state.turn_count >= max_turns:
                return "rate_limited"
            # Check minimum interval between turns
            if (
                state.last_turn_time > 0
                and (now - state.last_turn_time) < min_seconds_between
            ):
                return "rate_limited"
            # Update turn record
            state.turn_count += 1
            state.last_turn_time = now
            return None

    def check_daily_cap(self, daily_cap: int = 200) -> str | None:
        """Check if process-wide daily LLM call cap has been reached.

        Automatically resets counter when UTC date rolls over to midnight.
        Returns:
            'daily_cap_reached' if cap is exhausted, None if calls remain.
        """
        today = self._date_fn()
        with self._lock:
            if today != self._current_date:
                self._current_date = today
                self._daily_calls = 0

            if self._daily_calls >= daily_cap:
                return "daily_cap_reached"
            return None

    def record_llm_call(self) -> None:
        """Increment the process-wide daily LLM call count."""
        today = self._date_fn()
        with self._lock:
            if today != self._current_date:
                self._current_date = today
                self._daily_calls = 0
            self._daily_calls += 1

    @property
    def daily_calls(self) -> int:
        """Return current daily LLM call count."""
        with self._lock:
            return self._daily_calls


# Shared process-wide singleton
default_rate_limiter = RateLimiter()
