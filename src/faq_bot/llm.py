"""LLM integration layer for Google GenAI SDK."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from google import genai
from google.genai import errors, types

from faq_bot.config import Config, load_config
from faq_bot.models import BotReply, Message, Usage

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when LLM call fails permanently or exhausts retries."""


@dataclass
class LLMResult:
    """Result returned by generate_json."""

    text: str
    usage: Usage


def generate_json(
    system_prompt: str,
    contents: list[Message],
    config: Config | None = None,
    client: genai.Client | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> LLMResult:
    """Call Gemini to generate JSON structured output adhering to BotReply schema.

    Retries transient errors (429, 5xx) with 1s, 2s, 4s exponential backoff.
    Never retries permanent client errors (400, 401, 403).
    """
    cfg = config or load_config()
    cli = client or genai.Client(api_key=cfg.gemini_api_key)
    sleep = sleep_fn or time.sleep

    sdk_contents = [
        types.Content(role=msg.role, parts=[types.Part(text=msg.text)])
        for msg in contents
    ]

    req_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_json_schema=BotReply.model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.2,
        max_output_tokens=800,
    )

    max_retries = cfg.llm_max_retries
    wait = 1.0

    for attempt in range(max_retries + 1):
        try:
            response = cli.models.generate_content(
                model=cfg.gemini_model,
                contents=sdk_contents,
                config=req_config,
            )

            # Extract token counts
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                p_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
                tot_tokens = getattr(usage_meta, "total_token_count", 0) or 0
                out_tokens = max(0, tot_tokens - p_tokens)
                usage = Usage(input_tokens=p_tokens, output_tokens=out_tokens)
            else:
                logger.warning("Token usage metadata was missing from LLM response.")
                usage = Usage(input_tokens=0, output_tokens=0)

            resp_text = response.text or ""
            return LLMResult(text=resp_text, usage=usage)

        except errors.APIError as err:
            status_code = getattr(err, "code", None)
            # Permanent client errors
            if status_code in (400, 401, 403):
                raise LLMError(
                    f"Permanent LLM API error {status_code}: {err.message}"
                ) from err

            # Transient errors: 429 or 5xx
            if attempt < max_retries:
                logger.info(
                    "Transient API error %s on attempt %d; retrying in %fs",
                    status_code,
                    attempt + 1,
                    wait,
                )
                sleep(wait)
                wait *= 2.0
            else:
                raise LLMError(
                    f"LLM retries exhausted after {attempt + 1} attempts. Last error: {err}"
                ) from err

        except Exception as exc:
            if attempt < max_retries:
                logger.info(
                    "Transient exception %s on attempt %d; retrying in %fs",
                    type(exc).__name__,
                    attempt + 1,
                    wait,
                )
                sleep(wait)
                wait *= 2.0
            else:
                raise LLMError(
                    f"LLM call failed after {attempt + 1} attempts: {exc}"
                ) from exc

    raise LLMError("LLM call failed.")
