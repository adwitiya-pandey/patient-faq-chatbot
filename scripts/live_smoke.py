"""Live smoke test script to diagnose Gemini API calls."""

import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from faq_bot.config import load_config
from faq_bot.llm import LLMError, generate_json
from faq_bot.models import Message
from faq_bot.prompts import build_system_prompt


def redact_key(text: str, key: str | None) -> str:
    if key and key in text:
        return text.replace(key, "[REDACTED_API_KEY]")
    return text


def main() -> None:
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not found in environment or .env. Skipping live call.")
        sys.exit(0)

    try:
        cfg = load_config()
    except (ValueError, TypeError) as exc:
        print(f"Failed to load config: {exc}")
        sys.exit(1)

    print(f"Configured model: {cfg.gemini_model}")

    client = genai.Client(api_key=key)

    # Check model list first
    print("Checking available models via client.models.list()...")
    try:
        pager = client.models.list(config={"page_size": 100})
        models = [m.name for m in pager]
        print(f"Total models returned: {len(models)}")
        matched = [m for m in models if cfg.gemini_model in m]
        print(f"Models matching '{cfg.gemini_model}': {matched}")
    except Exception as e:  # noqa: BLE001 - diagnostic script catches any API failure
        msg = redact_key(str(e), key)
        print(f"client.models.list() failed: {type(e).__name__}: {msg}")

    # Now test generate_json with a plain FAQ question
    print("\nCalling generate_json with a plain FAQ question...")
    system_prompt = build_system_prompt(cfg.hospital_name)
    contents = [Message(role="user", text="What are the visiting hours?")]

    try:
        result = generate_json(
            system_prompt=system_prompt,
            contents=contents,
            config=cfg,
            client=client,
        )
        print("Call SUCCESSFUL!")
        print(f"Usage: {result.usage}")
        print(f"Response text: {result.text[:200]}")
    except LLMError as err:
        cause = err.__cause__
        status_code = getattr(cause, "code", None) if cause else None
        msg = redact_key(str(err), key)
        print("LLMError caught:")
        print(f"  Class: {type(err).__name__}")
        print(f"  Underlying cause class: {type(cause).__name__ if cause else 'None'}")
        print(f"  HTTP Status: {status_code}")
        print(f"  Message: {msg}")
    except errors.APIError as err:
        status_code = getattr(err, "code", None)
        msg = redact_key(err.message or str(err), key)
        print("APIError caught:")
        print(f"  Class: {type(err).__name__}")
        print(f"  HTTP Status: {status_code}")
        print(f"  Message: {msg}")
    except Exception as exc:  # noqa: BLE001 - diagnostic script reports unhandled exceptions
        msg = redact_key(str(exc), key)
        print("Exception caught:")
        print(f"  Class: {type(exc).__name__}")
        print("  HTTP Status: None")
        print(f"  Message: {msg}")


if __name__ == "__main__":
    main()
