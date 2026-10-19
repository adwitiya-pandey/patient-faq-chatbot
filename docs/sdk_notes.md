# SDK notes

Pre-filled on 18 Oct 2026 by running google-genai 2.31.0, anthropic 1.15.0, streamlit 1.66.0 and pydantic 2.12.5 in a throwaway Python 3.13.16 environment (no network calls). **The coding agent must re-run the probe below against the versions `uv` installs and correct this file where anything differs.** Anything not listed here is unverified: do not guess.

## google-genai (verified)
```python
from google import genai
from google.genai import types, errors
client = genai.Client(api_key=...)              # constructs offline
client.models.generate_content(model=..., contents=[...], config=types.GenerateContentConfig(...))
```
| Topic | Result |
|---|---|
| Config | `types.GenerateContentConfig(system_instruction=..., response_mime_type="application/json", response_json_schema=<Pydantic model_json_schema()>, temperature=0.2, max_output_tokens=400)` builds without error. Whether the API accepts that exact schema (for example `additionalProperties` from `extra="forbid"`) is **not verified**: the human live test (H7) is the proof. |
| Multi-turn contents | `[types.Content(role="user", parts=[types.Part(text="hi")]), types.Content(role="model", parts=[types.Part(text="hello")])]` builds. |
| Response text | `response.text` returns the first candidate's text. |
| Usage metadata | `response.usage_metadata.prompt_token_count`, `.candidates_token_count`, `.total_token_count`, `.thoughts_token_count`, `.cached_content_token_count`; any may be `None`: treat `None` as 0. Output tokens = `total_token_count - prompt_token_count` (this includes thinking tokens, which are billed as output). |
| Errors | `errors.APIError(code, response_json)` exposes `.code` (int), `.status` (str, e.g. `RESOURCE_EXHAUSTED`), `.message`; subclasses `errors.ClientError` (4xx) and `errors.ServerError` (5xx). Tests can build `errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})`. |
| Model | `gemini-3.8-flash` is listed Stable on the official models page (17 Oct 2026). Free tier: no charge. Paid price: USD 0.75 input and 3.75 output per 1M tokens through 31 Dec 2026, then 1.50 and 7.50. Free-tier rate limits: not verified. |

## anthropic (verified; only needed for the optional task H11)
| Topic | Result |
|---|---|
| Client | `from anthropic import Anthropic`; `Anthropic(api_key="...")` constructs offline. |
| Call | `client.messages.create(model=..., max_tokens=..., system=..., messages=[{"role": "user"|"assistant", "content": "..."}])`; the signature lists `max_tokens`, `messages`, `model`, `system` among its parameters. |
| Response | `Message` fields include `content` (list of blocks; text blocks have `.text`), `usage`, `stop_reason`. `Usage` has `input_tokens` and `output_tokens`. |
| Errors | `anthropic.APIError`, `APIStatusError`, `APIConnectionError`, `RateLimitError`, `AuthenticationError`, `APITimeoutError` exist. Status-code attribute name on `APIStatusError`: read the installed class before use. |
| Model ids | Anthropic's current API strings include `claude-haiku-5-5` and `claude-sonnet-5-5`. Pricing and key availability: not verified; the owner may have no API key. |

## Not verified
1. Whether the Gemini API accepts `response_json_schema` built from `BotReply.model_json_schema()` unchanged.
2. Free-tier rate limits and data-use terms for the Gemini model.
3. Streamlit `AppTest` rendering of `st.chat_input` in 1.66.0 (H5 decides with evidence).

## Probe (re-run; `uv run python -I probe.py` from a scratch folder, not committed)
```python
from typing import Literal

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ConfigDict, Field


class BotReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["faq", "clinical_advice", "emergency", "off_topic"]
    answer: str = Field(max_length=1200)


cfg = types.GenerateContentConfig(
    system_instruction="s",
    response_mime_type="application/json",
    response_json_schema=BotReply.model_json_schema(),
    temperature=0.2,
    max_output_tokens=400,
)
print("config ok:", cfg.response_mime_type)
contents = [
    types.Content(role="user", parts=[types.Part(text="hi")]),
    types.Content(role="model", parts=[types.Part(text="hello")]),
]
print("contents ok:", [c.role for c in contents])
usage = types.GenerateContentResponseUsageMetadata(
    prompt_token_count=10, candidates_token_count=5, total_token_count=20, thoughts_token_count=5
)
reply = types.GenerateContentResponse(
    usage_metadata=usage,
    candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text='{"category":"faq","answer":"x"}')]))],
)
print("text:", reply.text, "| output tokens:", usage.total_token_count - usage.prompt_token_count)
err = errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
print("APIError:", err.code, err.status, err.message)
print("client:", type(genai.Client(api_key="dummy")).__name__)
```
Expected output: `config ok: application/json`; `contents ok: ['user', 'model']`; `text: {"category":"faq","answer":"x"} | output tokens: 10`; `APIError: 429 RESOURCE_EXHAUSTED quota`; `client: Client`.
