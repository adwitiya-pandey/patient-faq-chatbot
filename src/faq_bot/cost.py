"""Token usage and cost estimation tracking."""

from dataclasses import dataclass

from faq_bot.models import Usage


def estimate_cost(usage: Usage, price_in: float, price_out: float) -> float:
    """Calculate estimated cost in USD based on input and output token counts."""
    return (
        usage.input_tokens * price_in + usage.output_tokens * price_out
    ) / 1_000_000.0


@dataclass
class Totals:
    """Running session totals for token usage and estimated cost."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    llm_calls: int = 0

    def add_call(self, usage: Usage, price_in: float, price_out: float) -> None:
        """Record an LLM call with its token usage and estimated cost."""
        if usage.input_tokens == 0 and usage.output_tokens == 0:
            return
        cost = estimate_cost(usage, price_in, price_out)
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.total_cost_usd += cost
        self.llm_calls += 1

    def reset(self) -> None:
        """Reset running session counters."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost_usd = 0.0
        self.llm_calls = 0
