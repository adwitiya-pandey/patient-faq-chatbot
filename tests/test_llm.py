"""Tests for LLM layer retry logic, backoff, and usage extraction."""

from unittest.mock import MagicMock

import pytest
from google.genai import errors, types

from faq_bot.config import Config
from faq_bot.llm import LLMError, generate_json
from faq_bot.models import Message


def test_retry_on_429_then_success():
    """Rate limit 429 retries with 1s, 2s, 4s backoff and succeeds on 4th attempt."""
    mock_client = MagicMock()
    sleeps: list[float] = []

    err_429 = errors.APIError(
        429,
        {"error": {"message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}},
    )
    ok_response = MagicMock()
    ok_response.text = '{"category": "faq", "answer": "The pharmacy is open 24 hours."}'
    ok_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=20, candidates_token_count=10, total_token_count=30
    )

    mock_client.models.generate_content.side_effect = [
        err_429,
        err_429,
        err_429,
        ok_response,
    ]

    cfg = Config(gemini_api_key="test-key", llm_max_retries=3)
    result = generate_json(
        system_prompt="system",
        contents=[Message(role="user", text="hello")],
        config=cfg,
        client=mock_client,
        sleep_fn=sleeps.append,
    )

    assert (
        result.text == '{"category": "faq", "answer": "The pharmacy is open 24 hours."}'
    )
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 10
    assert sleeps == [1.0, 2.0, 4.0]
    assert mock_client.models.generate_content.call_count == 4


def test_no_retry_on_401():
    """Client error 401 is permanent and must not be retried."""
    mock_client = MagicMock()
    sleeps: list[float] = []

    err_401 = errors.APIError(
        401, {"error": {"message": "Unauthorized", "status": "UNAUTHENTICATED"}}
    )
    mock_client.models.generate_content.side_effect = err_401

    cfg = Config(gemini_api_key="invalid-key", llm_max_retries=3)
    with pytest.raises(LLMError) as exc_info:
        generate_json(
            system_prompt="system",
            contents=[Message(role="user", text="hello")],
            config=cfg,
            client=mock_client,
            sleep_fn=sleeps.append,
        )

    assert (
        "401" in str(exc_info.value)
        or "UNAUTHENTICATED" in str(exc_info.value)
        or "Permanent" in str(exc_info.value)
    )
    assert sleeps == []
    assert mock_client.models.generate_content.call_count == 1


def test_gives_up_after_max_retries():
    """Exhausting LLM_MAX_RETRIES raises LLMError."""
    mock_client = MagicMock()
    sleeps: list[float] = []

    err_503 = errors.APIError(
        503, {"error": {"message": "Service unavailable", "status": "UNAVAILABLE"}}
    )
    mock_client.models.generate_content.side_effect = err_503

    cfg = Config(gemini_api_key="test-key", llm_max_retries=3)
    with pytest.raises(LLMError):
        generate_json(
            system_prompt="system",
            contents=[Message(role="user", text="hello")],
            config=cfg,
            client=mock_client,
            sleep_fn=sleeps.append,
        )

    # 1 initial + 3 retries = 4 calls, sleeps 1, 2, 4
    assert mock_client.models.generate_content.call_count == 4
    assert sleeps == [1.0, 2.0, 4.0]
