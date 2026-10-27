"""Pydantic data models for chat bot replies and turn results."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BotReply(BaseModel):
    """Structured response expected from the LLM."""

    model_config = ConfigDict(extra="forbid")
    category: Literal["faq", "clinical_advice", "emergency", "off_topic"]
    answer: str = Field(max_length=1200)


class Usage(BaseModel):
    """Token usage tracking for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0


class TurnResult(BaseModel):
    """Final result of processing a single conversation turn."""

    text: str
    category: str
    blocked: bool
    usage: Usage
    pii_redacted: bool
    guardrail_flags: list[str] = Field(default_factory=list)
    request_id: str = ""
    latency_ms: float = 0.0


@dataclass
class Message:
    """Internal message representation for conversation history."""

    role: Literal["user", "model"]
    text: str
