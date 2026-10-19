"""Chat turn pipeline and conversation orchestration."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from faq_bot.config import Config, load_config
from faq_bot.llm import generate_json
from faq_bot.messages import (
    CLINICAL_REFUSAL_TEXT,
    EMERGENCY_TEXT,
    EMPTY_TEXT,
    FALLBACK_TEXT,
    LLM_ERROR_TEXT,
    OFF_TOPIC_TEXT,
    TOO_LONG_TEXT,
)
from faq_bot.models import BotReply, Message, TurnResult, Usage
from faq_bot.prompts import build_system_prompt
from faq_bot.safety import output_guard, precheck, redact_pii, validate_input

logger = logging.getLogger("faq_bot.chat")


def _log_turn_metadata(
    start_time: float,
    category: str,
    blocked: bool,
    pii_redacted: bool,
    usage: Usage,
    model: str,
) -> None:
    """Emit exactly one metadata-only log line without message text (SPEC 15, S4)."""
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    ts = datetime.now(UTC).isoformat()
    logger.info(
        "Turn completed: timestamp=%s category=%s blocked=%s pii_redacted=%s "
        "input_tokens=%d output_tokens=%d latency_ms=%.2f model=%s",
        ts,
        category,
        blocked,
        pii_redacted,
        usage.input_tokens,
        usage.output_tokens,
        latency_ms,
        model,
    )


def handle_turn(
    history: list[dict[str, Any] | Message],
    text: str,
    llm: Any | None = None,
    config: Config | None = None,
) -> TurnResult:
    """Process a single turn following the 10-step turn pipeline (SPEC 5).

    Returns:
        TurnResult containing text, category, blocked, usage, and pii_redacted.
    """
    start_time = time.perf_counter()
    cfg = config or load_config()

    # Step 1: Validate input
    clean_text, val_err = validate_input(text, max_chars=cfg.max_input_chars)
    if val_err == "empty":
        usage = Usage()
        _log_turn_metadata(
            start_time, "invalid_input", True, False, usage, cfg.gemini_model
        )
        return TurnResult(
            text=EMPTY_TEXT,
            category="invalid_input",
            blocked=True,
            usage=usage,
            pii_redacted=False,
        )
    if val_err == "too_long":
        usage = Usage()
        _log_turn_metadata(
            start_time, "invalid_input", True, False, usage, cfg.gemini_model
        )
        return TurnResult(
            text=TOO_LONG_TEXT,
            category="invalid_input",
            blocked=True,
            usage=usage,
            pii_redacted=False,
        )

    # Step 2: Redact PII
    text_for_llm, pii_found = redact_pii(clean_text)

    # Step 3: Pre-check before LLM
    pre_hit = precheck(text_for_llm)
    if pre_hit == "emergency":
        usage = Usage()
        _log_turn_metadata(
            start_time, "emergency", True, pii_found, usage, cfg.gemini_model
        )
        return TurnResult(
            text=EMERGENCY_TEXT,
            category="emergency",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
        )
    if pre_hit == "clinical_advice":
        usage = Usage()
        _log_turn_metadata(
            start_time, "clinical_advice", True, pii_found, usage, cfg.gemini_model
        )
        return TurnResult(
            text=CLINICAL_REFUSAL_TEXT,
            category="clinical_advice",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
        )

    # Step 4: Build contents from last N non-blocked turns
    allowed_messages: list[Message] = []
    for item in history:
        if isinstance(item, Message):
            allowed_messages.append(item)
        elif isinstance(item, dict):
            # Exclude blocked turns from model context
            if item.get("blocked", False) is True:
                continue
            cat = item.get("category")
            if cat and cat != "faq":
                continue
            role = item.get("role")
            content = item.get("content", "")
            if role in ("user", "human"):
                allowed_messages.append(Message(role="user", text=content))
            elif role in ("assistant", "model"):
                allowed_messages.append(Message(role="model", text=content))

    # Keep at most max_history_turns pairs (2 * max_history_turns messages)
    max_history_messages = cfg.max_history_turns * 2
    if len(allowed_messages) > max_history_messages:
        allowed_messages = allowed_messages[-max_history_messages:]

    # Append current turn user message
    allowed_messages.append(Message(role="user", text=text_for_llm))

    # Step 5: Call LLM
    system_prompt = build_system_prompt(cfg.hospital_name)
    llm_callable = getattr(llm, "generate_json", llm) or generate_json

    try:
        llm_result = llm_callable(
            system_prompt=system_prompt, contents=allowed_messages, config=cfg
        )
    except Exception as exc:  # noqa: BLE001 - user-facing app must not crash on unexpected LLM failures
        logger.warning("LLM call failed with error: %s", type(exc).__name__)
        usage = Usage()
        _log_turn_metadata(
            start_time, "llm_error", True, pii_found, usage, cfg.gemini_model
        )
        return TurnResult(
            text=LLM_ERROR_TEXT,
            category="llm_error",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
        )

    # Step 6: Parse JSON -> BotReply (retry once if invalid)
    total_usage = Usage(
        input_tokens=llm_result.usage.input_tokens,
        output_tokens=llm_result.usage.output_tokens,
    )
    bot_reply: BotReply | None = None
    try:
        bot_reply = BotReply.model_validate_json(llm_result.text)
    except (ValidationError, json.JSONDecodeError, ValueError):
        # Retry once
        try:
            llm_result_retry = llm_callable(
                system_prompt=system_prompt, contents=allowed_messages, config=cfg
            )
            total_usage.input_tokens += llm_result_retry.usage.input_tokens
            total_usage.output_tokens += llm_result_retry.usage.output_tokens
            bot_reply = BotReply.model_validate_json(llm_result_retry.text)
        except Exception:  # noqa: BLE001 - parse fallback must catch any decoding/validation failure
            _log_turn_metadata(
                start_time,
                "unparseable",
                True,
                pii_found,
                total_usage,
                cfg.gemini_model,
            )
            return TurnResult(
                text=FALLBACK_TEXT,
                category="unparseable",
                blocked=True,
                usage=total_usage,
                pii_redacted=pii_found,
            )

    # Step 7: Combine categories; refusals use fixed text
    reply_category = bot_reply.category
    if reply_category == "emergency":
        final_category = "emergency"
        reply_text = EMERGENCY_TEXT
        blocked = True
    elif reply_category == "clinical_advice":
        final_category = "clinical_advice"
        reply_text = CLINICAL_REFUSAL_TEXT
        blocked = True
    elif reply_category == "off_topic":
        final_category = "off_topic"
        reply_text = OFF_TOPIC_TEXT
        blocked = True
    else:  # faq
        final_category = "faq"
        reply_text = bot_reply.answer
        blocked = False

    # Step 8: Output guard (dose-like numbers in answers) -> fixed message
    if not blocked and output_guard(reply_text):
        final_category = "clinical_advice"
        reply_text = CLINICAL_REFUSAL_TEXT
        blocked = True

    # Step 9 & 10: Emit log line and return TurnResult
    _log_turn_metadata(
        start_time, final_category, blocked, pii_found, total_usage, cfg.gemini_model
    )
    return TurnResult(
        text=reply_text,
        category=final_category,
        blocked=blocked,
        usage=total_usage,
        pii_redacted=pii_found,
    )
