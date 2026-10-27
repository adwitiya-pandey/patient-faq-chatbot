"""Chat turn pipeline and conversation orchestration."""

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from faq_bot.config import Config, load_config
from faq_bot.cost import estimate_cost
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
logger.setLevel(logging.INFO)


def _log_turn_metadata(
    start_time: float,
    category: str,
    blocked: bool,
    pii_redacted: bool,
    usage: Usage,
    model: str,
    llm_called: bool = False,
    request_id: str = "",
    session_id: str = "",
    guardrail_flags: list[str] | None = None,
    outcome: str = "",
    price_in: float = 0.75,
    price_out: float = 3.75,
) -> float:
    """Emit exactly one metadata-only log line without message text (SPEC 15, S4).

    Populates both conventional formatting and structured JSON event payload.
    """
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    ts = datetime.now(UTC).isoformat()
    flags = list(guardrail_flags or [])
    if pii_redacted and "pii_redacted" not in flags:
        flags.append("pii_redacted")

    est_cost = estimate_cost(usage, price_in=price_in, price_out=price_out)

    event_payload = {
        "timestamp": ts,
        "request_id": request_id,
        "session_id": session_id,
        "category": category,
        "llm_called": llm_called,
        "model": model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "est_cost_usd": est_cost,
        "latency_ms": latency_ms,
        "guardrail_flags": flags,
        "outcome": outcome,
    }

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
        extra={"structured_event": event_payload},
    )
    return latency_ms


def handle_turn(
    history: list[dict[str, Any] | Message],
    text: str,
    llm: Any | None = None,
    config: Config | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> TurnResult:
    """Process a single turn following the 10-step turn pipeline (SPEC 5).

    Returns:
        TurnResult containing text, category, blocked, usage, pii_redacted, and audit metadata.
    """
    start_time = time.perf_counter()
    cfg = config or load_config()
    req_id = request_id or str(uuid.uuid4())
    sess_id = session_id or uuid.uuid4().hex[:16]

    # Step 1: Validate input
    clean_text, val_err = validate_input(text, max_chars=cfg.max_input_chars)
    if val_err == "empty":
        usage = Usage()
        lat_ms = _log_turn_metadata(
            start_time,
            category="invalid_input",
            blocked=True,
            pii_redacted=False,
            usage=usage,
            model=cfg.gemini_model,
            llm_called=False,
            request_id=req_id,
            session_id=sess_id,
            guardrail_flags=[],
            outcome="rejected",
            price_in=cfg.price_input_per_m,
            price_out=cfg.price_output_per_m,
        )
        return TurnResult(
            text=EMPTY_TEXT,
            category="invalid_input",
            blocked=True,
            usage=usage,
            pii_redacted=False,
            guardrail_flags=[],
            request_id=req_id,
            latency_ms=lat_ms,
        )
    if val_err == "too_long":
        usage = Usage()
        flags = ["input_too_long"]
        lat_ms = _log_turn_metadata(
            start_time,
            category="invalid_input",
            blocked=True,
            pii_redacted=False,
            usage=usage,
            model=cfg.gemini_model,
            llm_called=False,
            request_id=req_id,
            session_id=sess_id,
            guardrail_flags=flags,
            outcome="rejected",
            price_in=cfg.price_input_per_m,
            price_out=cfg.price_output_per_m,
        )
        return TurnResult(
            text=TOO_LONG_TEXT,
            category="invalid_input",
            blocked=True,
            usage=usage,
            pii_redacted=False,
            guardrail_flags=flags,
            request_id=req_id,
            latency_ms=lat_ms,
        )

    # Step 2: Redact PII
    text_for_llm, pii_found = redact_pii(clean_text)

    # Step 3: Pre-check before LLM
    pre_hit = precheck(text_for_llm)
    if pre_hit == "emergency":
        usage = Usage()
        flags = ["emergency_precheck"]
        if pii_found:
            flags.append("pii_redacted")
        lat_ms = _log_turn_metadata(
            start_time,
            category="emergency",
            blocked=True,
            pii_redacted=pii_found,
            usage=usage,
            model=cfg.gemini_model,
            llm_called=False,
            request_id=req_id,
            session_id=sess_id,
            guardrail_flags=flags,
            outcome="refused",
            price_in=cfg.price_input_per_m,
            price_out=cfg.price_output_per_m,
        )
        return TurnResult(
            text=EMERGENCY_TEXT,
            category="emergency",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
            guardrail_flags=flags,
            request_id=req_id,
            latency_ms=lat_ms,
        )
    if pre_hit == "clinical_advice":
        usage = Usage()
        flags = ["clinical_precheck"]
        if pii_found:
            flags.append("pii_redacted")
        lat_ms = _log_turn_metadata(
            start_time,
            category="clinical_advice",
            blocked=True,
            pii_redacted=pii_found,
            usage=usage,
            model=cfg.gemini_model,
            llm_called=False,
            request_id=req_id,
            session_id=sess_id,
            guardrail_flags=flags,
            outcome="refused",
            price_in=cfg.price_input_per_m,
            price_out=cfg.price_output_per_m,
        )
        return TurnResult(
            text=CLINICAL_REFUSAL_TEXT,
            category="clinical_advice",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
            guardrail_flags=flags,
            request_id=req_id,
            latency_ms=lat_ms,
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
        flags = ["pii_redacted"] if pii_found else []
        lat_ms = _log_turn_metadata(
            start_time,
            category="llm_error",
            blocked=True,
            pii_redacted=pii_found,
            usage=usage,
            model=cfg.gemini_model,
            llm_called=True,
            request_id=req_id,
            session_id=sess_id,
            guardrail_flags=flags,
            outcome="error",
            price_in=cfg.price_input_per_m,
            price_out=cfg.price_output_per_m,
        )
        return TurnResult(
            text=LLM_ERROR_TEXT,
            category="llm_error",
            blocked=True,
            usage=usage,
            pii_redacted=pii_found,
            guardrail_flags=flags,
            request_id=req_id,
            latency_ms=lat_ms,
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
            flags = ["pii_redacted"] if pii_found else []
            lat_ms = _log_turn_metadata(
                start_time,
                category="unparseable",
                blocked=True,
                pii_redacted=pii_found,
                usage=total_usage,
                model=cfg.gemini_model,
                llm_called=True,
                request_id=req_id,
                session_id=sess_id,
                guardrail_flags=flags,
                outcome="error",
                price_in=cfg.price_input_per_m,
                price_out=cfg.price_output_per_m,
            )
            return TurnResult(
                text=FALLBACK_TEXT,
                category="unparseable",
                blocked=True,
                usage=total_usage,
                pii_redacted=pii_found,
                guardrail_flags=flags,
                request_id=req_id,
                latency_ms=lat_ms,
            )

    # Step 7: Combine categories; refusals use fixed text
    reply_category = bot_reply.category
    if reply_category == "emergency":
        final_category = "emergency"
        reply_text = EMERGENCY_TEXT
        blocked = True
        outcome = "refused"
    elif reply_category == "clinical_advice":
        final_category = "clinical_advice"
        reply_text = CLINICAL_REFUSAL_TEXT
        blocked = True
        outcome = "refused"
    elif reply_category == "off_topic":
        final_category = "off_topic"
        reply_text = OFF_TOPIC_TEXT
        blocked = True
        outcome = "off_topic"
    else:  # faq
        final_category = "faq"
        reply_text = bot_reply.answer
        blocked = False
        outcome = "answered"

    flags = ["pii_redacted"] if pii_found else []

    # Step 8: Output guard (dose-like numbers in answers) -> fixed message
    if not blocked and output_guard(reply_text):
        final_category = "clinical_advice"
        reply_text = CLINICAL_REFUSAL_TEXT
        blocked = True
        outcome = "refused"
        flags.append("output_dose_blocked")

    # Step 9 & 10: Emit log line and return TurnResult
    lat_ms = _log_turn_metadata(
        start_time,
        category=final_category,
        blocked=blocked,
        pii_redacted=pii_found,
        usage=total_usage,
        model=cfg.gemini_model,
        llm_called=True,
        request_id=req_id,
        session_id=sess_id,
        guardrail_flags=flags,
        outcome=outcome,
        price_in=cfg.price_input_per_m,
        price_out=cfg.price_output_per_m,
    )
    return TurnResult(
        text=reply_text,
        category=final_category,
        blocked=blocked,
        usage=total_usage,
        pii_redacted=pii_found,
        guardrail_flags=flags,
        request_id=req_id,
        latency_ms=lat_ms,
    )
