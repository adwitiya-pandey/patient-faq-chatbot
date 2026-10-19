"""Tests for token usage and cost estimation."""

import pytest

from faq_bot.cost import Totals, estimate_cost
from faq_bot.models import Usage


def test_estimate_cost_known_values():
    """Known token counts return mathematically exact estimated USD cost."""
    # 1,000,000 input tokens at $0.75 + 1,000,000 output tokens at $3.75 = $4.50
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = estimate_cost(usage, price_in=0.75, price_out=3.75)
    assert pytest.approx(cost, rel=1e-6) == 4.50

    # 1,000 in, 500 out -> (750 + 1875) / 1,000,000 = 0.002625
    small_usage = Usage(input_tokens=1000, output_tokens=500)
    small_cost = estimate_cost(small_usage, price_in=0.75, price_out=3.75)
    assert pytest.approx(small_cost, rel=1e-6) == 0.002625


def test_estimate_cost_zero_usage():
    """Zero usage results in zero cost."""
    zero_usage = Usage(input_tokens=0, output_tokens=0)
    cost = estimate_cost(zero_usage, price_in=0.75, price_out=3.75)
    assert cost == 0.0


def test_totals_running_tracking():
    """Totals dataclass tracks cumulative usage, calls, and cost correctly."""
    totals = Totals()
    assert totals.input_tokens == 0
    assert totals.output_tokens == 0
    assert totals.total_cost_usd == 0.0
    assert totals.llm_calls == 0

    # Adding a zero-token turn adds nothing
    totals.add_call(
        Usage(input_tokens=0, output_tokens=0), price_in=0.75, price_out=3.75
    )
    assert totals.llm_calls == 0
    assert totals.total_cost_usd == 0.0

    # First real call
    totals.add_call(
        Usage(input_tokens=100, output_tokens=50), price_in=0.75, price_out=3.75
    )
    assert totals.llm_calls == 1
    assert totals.input_tokens == 100
    assert totals.output_tokens == 50
    expected_cost_1 = (100 * 0.75 + 50 * 3.75) / 1_000_000
    assert pytest.approx(totals.total_cost_usd, rel=1e-6) == expected_cost_1

    # Second real call
    totals.add_call(
        Usage(input_tokens=200, output_tokens=100), price_in=0.75, price_out=3.75
    )
    assert totals.llm_calls == 2
    assert totals.input_tokens == 300
    assert totals.output_tokens == 150
    expected_cost_2 = (300 * 0.75 + 150 * 3.75) / 1_000_000
    assert pytest.approx(totals.total_cost_usd, rel=1e-6) == expected_cost_2

    # Reset
    totals.reset()
    assert totals.llm_calls == 0
    assert totals.input_tokens == 0
    assert totals.output_tokens == 0
    assert totals.total_cost_usd == 0.0
