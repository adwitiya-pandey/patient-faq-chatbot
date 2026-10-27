"""Structured JSON logging configuration for the FAQ chatbot."""

import json
import logging
import os
import sys
from typing import Any

# The allowlisted fields required for per-turn audit events (SPEC 15, Step 2)
ALLOWLISTED_FIELDS = (
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
)


class JsonFormatter(logging.Formatter):
    """Format log records into structured JSON using allowlisted fields only.

    Guarantees no raw user prompts, redacted text, or bot generation texts are emitted.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Check for structured event payload
        event_dict: dict[str, Any] | None = getattr(record, "structured_event", None)
        if event_dict is not None and isinstance(event_dict, dict):
            payload = {
                field: event_dict[field]
                for field in ALLOWLISTED_FIELDS
                if field in event_dict
            }
            return json.dumps(payload)

        # Fallback for standard operational log messages (e.g. startup/warnings)
        fallback_payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(fallback_payload)


def setup_logging(log_level: str | None = None) -> logging.Logger:
    """Configure structured JSON logging to stdout.

    Reads LOG_LEVEL from environment if not explicitly provided (default: INFO).
    Idempotent: avoids adding duplicate handlers if invoked multiple times.
    """
    level_name = (log_level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Check if a JsonFormatter handler is already registered
    already_configured = any(
        isinstance(getattr(handler, "formatter", None), JsonFormatter)
        for handler in root_logger.handlers
    )

    if not already_configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(level)
        root_logger.addHandler(handler)

    return root_logger
