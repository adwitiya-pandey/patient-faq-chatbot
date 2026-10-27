"""Tests for structured JSON logging (Step 2)."""

import io
import json
import logging
from unittest.mock import patch

from faq_bot.chat import handle_turn
from faq_bot.config import Config
from faq_bot.logging_setup import ALLOWLISTED_FIELDS, JsonFormatter, setup_logging
from tests.fakes import FakeLLM


def test_allowlisted_fields_definition():
    """Verify all 12 required fields are specified in ALLOWLISTED_FIELDS."""
    expected = {
        "timestamp",
        "request_id",
        "session_id",
        "category",
        "llm_called",
        "model",
        "input_tokens",
        "output_tokens",
        "est_cost_usd",
        "latency_ms",
        "guardrail_flags",
        "outcome",
    }
    assert set(ALLOWLISTED_FIELDS) == expected


def test_json_formatter_structured_event():
    """Verify JsonFormatter formats structured_event records with allowlisted fields only."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="faq_bot.chat",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Turn completed: test",
        args=(),
        exc_info=None,
    )
    record.structured_event = {
        "timestamp": "2026-10-27T12:00:00Z",
        "request_id": "req-123",
        "session_id": "sess-456",
        "category": "faq",
        "llm_called": True,
        "model": "gemini-3.8-flash",
        "input_tokens": 100,
        "output_tokens": 50,
        "est_cost_usd": 0.0002,
        "latency_ms": 120.5,
        "guardrail_flags": ["pii_redacted"],
        "outcome": "answered",
        "forbidden_private_key": "should_not_be_included",
    }

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert set(data.keys()) == set(ALLOWLISTED_FIELDS)
    assert "forbidden_private_key" not in data
    assert data["request_id"] == "req-123"
    assert data["llm_called"] is True
    assert data["guardrail_flags"] == ["pii_redacted"]
    assert data["outcome"] == "answered"


def test_turn_log_fields_present_and_forbidden_content_absent():
    """Feed message containing email and phone; assert all allowlisted fields present and secrets absent."""
    email = "secret_patient_john@example.com"
    phone = "9876543210"
    user_prompt = (
        f"Hello my email is {email} and phone is {phone}. What are the visiting hours?"
    )
    bot_answer = "Visiting hours are 8:00 AM to 8:00 PM."

    fake_llm = FakeLLM([f'{{"category": "faq", "answer": "{bot_answer}"}}'])
    cfg = Config(gemini_api_key="test-key")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.INFO)

    chat_logger = logging.getLogger("faq_bot.chat")
    chat_logger.setLevel(logging.INFO)
    chat_logger.addHandler(handler)
    try:
        res = handle_turn(
            history=[],
            text=user_prompt,
            llm=fake_llm,
            config=cfg,
            session_id="custom-session-123",
            request_id="custom-req-789",
        )
        assert res.category == "faq"
        assert res.pii_redacted is True
    finally:
        chat_logger.removeHandler(handler)

    output = stream.getvalue().strip()
    assert output, "Expected structured JSON log output"

    log_obj = json.loads(output)

    # 1. Assert all 12 allowlisted fields are present
    for field in ALLOWLISTED_FIELDS:
        assert field in log_obj, f"Missing required field: {field}"

    # 2. Assert values
    assert log_obj["request_id"] == "custom-req-789"
    assert log_obj["session_id"] == "custom-session-123"
    assert log_obj["category"] == "faq"
    assert log_obj["llm_called"] is True
    assert log_obj["model"] == cfg.gemini_model
    assert isinstance(log_obj["input_tokens"], int)
    assert isinstance(log_obj["output_tokens"], int)
    assert isinstance(log_obj["est_cost_usd"], (int, float))
    assert isinstance(log_obj["latency_ms"], (int, float))
    assert "pii_redacted" in log_obj["guardrail_flags"]
    assert log_obj["outcome"] == "answered"

    # 3. Assert forbidden content is ABSENT across entire JSON log line
    assert email not in output
    assert phone not in output
    assert user_prompt not in output
    assert bot_answer not in output
    assert "visiting hours" not in output


def test_setup_logging_idempotence():
    """Verify setup_logging registers handler and does not duplicate handlers."""
    with patch("os.environ.get", return_value="DEBUG"):
        l1 = setup_logging()
        count1 = len(l1.handlers)
        l2 = setup_logging()
        count2 = len(l2.handlers)
        assert count1 == count2
