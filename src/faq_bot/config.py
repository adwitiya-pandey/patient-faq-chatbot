"""Configuration and environment variable management."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    gemini_api_key: str
    gemini_model: str = "gemini-3.8-flash"
    price_input_per_m: float = 0.75
    price_output_per_m: float = 3.75
    max_history_turns: int = 10
    max_input_chars: int = 500
    llm_max_retries: int = 3
    hospital_name: str = "Northfield Multispecialty Hospital"
    max_turns_per_session: int = 30
    min_seconds_between_turns: float = 2.0
    daily_llm_call_cap: int = 200
    llm_kill_switch: bool = False

    def __repr__(self) -> str:
        """Never echo the raw API key in string representations."""
        return (
            f"Config(gemini_api_key='***', gemini_model='{self.gemini_model}', "
            f"price_input_per_m={self.price_input_per_m}, price_output_per_m={self.price_output_per_m}, "
            f"max_history_turns={self.max_history_turns}, max_input_chars={self.max_input_chars}, "
            f"llm_max_retries={self.llm_max_retries}, hospital_name='{self.hospital_name}', "
            f"max_turns_per_session={self.max_turns_per_session}, "
            f"min_seconds_between_turns={self.min_seconds_between_turns}, "
            f"daily_llm_call_cap={self.daily_llm_call_cap}, "
            f"llm_kill_switch={self.llm_kill_switch})"
        )


def load_config(env: dict[str, str] | None = None) -> Config:
    """Load configuration from environment or provided dict.

    Raises:
        ValueError: If GEMINI_API_KEY is not set or empty. Never includes key value in the error message.
    """
    if env is None:
        load_dotenv()
        source = os.environ
    else:
        source = env

    api_key = source.get("GEMINI_API_KEY")
    if not api_key or not str(api_key).strip():
        raise ValueError("GEMINI_API_KEY environment variable is required")

    try:
        price_in = float(source.get("PRICE_INPUT_PER_M", 0.75))
    except (ValueError, TypeError):
        raise ValueError("PRICE_INPUT_PER_M must be a valid float") from None

    try:
        price_out = float(source.get("PRICE_OUTPUT_PER_M", 3.75))
    except (ValueError, TypeError):
        raise ValueError("PRICE_OUTPUT_PER_M must be a valid float") from None

    try:
        max_history = int(source.get("MAX_HISTORY_TURNS", 10))
    except (ValueError, TypeError):
        raise ValueError("MAX_HISTORY_TURNS must be a valid integer") from None

    try:
        max_chars = int(source.get("MAX_INPUT_CHARS", 500))
    except (ValueError, TypeError):
        raise ValueError("MAX_INPUT_CHARS must be a valid integer") from None

    try:
        max_retries = int(source.get("LLM_MAX_RETRIES", 3))
    except (ValueError, TypeError):
        raise ValueError("LLM_MAX_RETRIES must be a valid integer") from None

    try:
        max_turns = int(source.get("MAX_TURNS_PER_SESSION", 30))
    except (ValueError, TypeError):
        raise ValueError("MAX_TURNS_PER_SESSION must be a valid integer") from None

    try:
        min_seconds = float(source.get("MIN_SECONDS_BETWEEN_TURNS", 2.0))
    except (ValueError, TypeError):
        raise ValueError("MIN_SECONDS_BETWEEN_TURNS must be a valid float") from None

    try:
        daily_cap = int(source.get("DAILY_LLM_CALL_CAP", 200))
    except (ValueError, TypeError):
        raise ValueError("DAILY_LLM_CALL_CAP must be a valid integer") from None

    kill_switch_raw = source.get("LLM_KILL_SWITCH", "false")
    kill_switch = str(kill_switch_raw).strip().lower() in ("true", "1", "yes")

    model = source.get("GEMINI_MODEL", "gemini-3.8-flash")
    hospital = source.get("HOSPITAL_NAME", "Northfield Multispecialty Hospital")

    return Config(
        gemini_api_key=api_key.strip(),
        gemini_model=model.strip(),
        price_input_per_m=price_in,
        price_output_per_m=price_out,
        max_history_turns=max_history,
        max_input_chars=max_chars,
        llm_max_retries=max_retries,
        hospital_name=hospital.strip(),
        max_turns_per_session=max_turns,
        min_seconds_between_turns=min_seconds,
        daily_llm_call_cap=daily_cap,
        llm_kill_switch=kill_switch,
    )
