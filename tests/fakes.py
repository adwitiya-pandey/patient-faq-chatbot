"""Fake LLM implementation for offline testing without network access."""

from typing import Any

from faq_bot.models import Message, Usage


class FakeLLMResult:
    """Mock result matching llm.LLMResult interface."""

    def __init__(self, text: str, usage: Usage | None = None):
        self.text = text
        self.usage = usage or Usage(input_tokens=10, output_tokens=10)


class FakeLLM:
    """Mock LLM returning scripted responses or raising scripted errors."""

    def __init__(self, responses: list[Any] | None = None):
        self.responses: list[Any] = list(responses) if responses else []
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self, system_prompt: str, contents: list[Message], **kwargs: Any
    ) -> FakeLLMResult:
        """Record the call and return next scripted response."""
        self.calls.append(
            {"system_prompt": system_prompt, "contents": contents, "kwargs": kwargs}
        )

        if not self.responses:
            return FakeLLMResult(
                text='{"category": "faq", "answer": "Default mocked answer."}',
                usage=Usage(input_tokens=15, output_tokens=10),
            )

        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        if isinstance(resp, str):
            return FakeLLMResult(
                text=resp, usage=Usage(input_tokens=15, output_tokens=10)
            )
        return resp
