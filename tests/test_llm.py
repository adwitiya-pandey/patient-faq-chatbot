"""Tests for LLM layer retry logic, backoff, and usage extraction."""

from unittest.mock import MagicMock

import pytest
from google.genai import errors, types

from faq_bot.config import Config
from faq_bot.llm import LLMError, build_generate_content_config, generate_json
from faq_bot.models import BotReply, Message


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


def test_build_generate_content_config():
    """Verify GenerateContentConfig builds with correct schema, MIME type, and thinking parameters."""
    cfg = build_generate_content_config(
        system_prompt="system instructions", disable_thinking=True
    )
    assert cfg.system_instruction == "system instructions"
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_json_schema == BotReply.model_json_schema()
    assert cfg.temperature == 0.2
    assert cfg.max_output_tokens == 800
    assert cfg.thinking_config is not None
    assert cfg.thinking_config.thinking_budget == 0

    cfg_no_think = build_generate_content_config(
        system_prompt="sys", disable_thinking=False
    )
    assert cfg_no_think.thinking_config is None
