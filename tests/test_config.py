"""Tests for configuration loading and validation."""

import pytest

from faq_bot.config import Config, load_config


def test_missing_api_key_raises():
    """Missing GEMINI_API_KEY raises ValueError."""
    with pytest.raises(
        ValueError, match="GEMINI_API_KEY environment variable is required"
    ):
        load_config(env={})


def test_empty_api_key_raises():
    """Empty GEMINI_API_KEY raises ValueError."""
    with pytest.raises(
        ValueError, match="GEMINI_API_KEY environment variable is required"
    ):
        load_config(env={"GEMINI_API_KEY": "   "})


def test_config_defaults():
    """Default values are properly applied when only API key is supplied."""
    cfg = load_config(env={"GEMINI_API_KEY": "dummy-key"})
    assert cfg.gemini_api_key == "dummy-key"
    assert cfg.gemini_model == "gemini-3.8-flash"
    assert cfg.price_input_per_m == 0.75
    assert cfg.price_output_per_m == 3.75
    assert cfg.max_history_turns == 10
    assert cfg.max_input_chars == 500
    assert cfg.llm_max_retries == 3
    assert cfg.hospital_name == "Northfield Multispecialty Hospital"
    assert cfg.max_turns_per_session == 30
    assert cfg.min_seconds_between_turns == 2.0
    assert cfg.daily_llm_call_cap == 200
    assert cfg.llm_kill_switch is False


def test_config_custom_values():
    """Custom environment values override defaults."""
    custom_env = {
        "GEMINI_API_KEY": "custom-key",
        "GEMINI_MODEL": "gemini-2.5-flash",
        "PRICE_INPUT_PER_M": "1.50",
        "PRICE_OUTPUT_PER_M": "7.50",
        "MAX_HISTORY_TURNS": "5",
        "MAX_INPUT_CHARS": "300",
        "LLM_MAX_RETRIES": "2",
        "HOSPITAL_NAME": "Bengaluru General Hospital",
        "MAX_TURNS_PER_SESSION": "15",
        "MIN_SECONDS_BETWEEN_TURNS": "3.5",
        "DAILY_LLM_CALL_CAP": "100",
        "LLM_KILL_SWITCH": "true",
    }
    cfg = load_config(env=custom_env)
    assert cfg.gemini_api_key == "custom-key"
    assert cfg.gemini_model == "gemini-2.5-flash"
    assert cfg.price_input_per_m == 1.50
    assert cfg.price_output_per_m == 7.50
    assert cfg.max_history_turns == 5
    assert cfg.max_input_chars == 300
    assert cfg.llm_max_retries == 2
    assert cfg.hospital_name == "Bengaluru General Hospital"
    assert cfg.max_turns_per_session == 15
    assert cfg.min_seconds_between_turns == 3.5
    assert cfg.daily_llm_call_cap == 100
    assert cfg.llm_kill_switch is True


def test_config_repr_does_not_echo_key():
    """Config __repr__ masks the API key."""
    cfg = Config(gemini_api_key="SecretKey123456789")
    repr_str = repr(cfg)
    assert "SecretKey123456789" not in repr_str
    assert "***" in repr_str
