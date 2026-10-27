# Northfield Hospital Patient FAQ Chatbot

[![CI](https://github.com/adwitiya-pandey/patient-faq-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/adwitiya-pandey/patient-faq-chatbot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade patient FAQ assistant for a fictional hospital in Bengaluru, built in raw Python using the official Google GenAI SDK (`google-genai`), Streamlit, and `pytest`. It demonstrates deterministic safety guardrails, structured JSON output enforcement, metadata-only JSON logging, offline scripted demonstration, rate limiting, output grounding, and an authentic Git merge conflict resolution history.

---

## What and Why

Northfield Multispecialty Hospital in Bengaluru receives over 400 calls daily at its front desk, with approximately 70% asking the same routine logistical questions about appointments, insurance, surgery preparation, and pharmacy hours. This automated chat assistant handles recurring logistics inquiries at any hour without keeping patients waiting on hold. Crucially, the system enforces strict deterministic safety layers so that the bot never diagnoses symptoms, never prescribes or doses medicines, and immediately redirects emergencies to the 24-hour emergency desk.

---

## Live Demo & Container Deployment

An Azure Container Apps deployment pipeline packages this application into a multi-stage container and deploys with **scale-to-zero** serverless autoscaling to guarantee **$0.00 idle operational cost**.

- **Deployment Guide:** Complete step-by-step instructions in [docs/DEPLOY.md](docs/DEPLOY.md).
- **Public Container Image:** `ghcr.io/adwitiya-pandey/patient-faq-chatbot:latest`
- **Sample Endpoint URL:** `https://faq-bot-app.<custom-or-azure-domain>.azurecontainerapps.io`

```mermaid
flowchart LR
    Dev["GitHub Tag (v*)"] --> GHA["GitHub Actions\n(publish-image.yml)"]
    GHA --> GHCR["GitHub Container Registry\n(ghcr.io)"]
    GHCR --> ACA["Azure Container Apps\n(min=0, max=1)"]
    ACA --> App["Streamlit Chatbot\n(:8501)"]
    App --> Gemini["Gemini API\n(gemini-3.8-flash)"]
```

> [!NOTE]
> **Cold Start Notice:** The deployment configures `--min-replicas 0` to eliminate cloud idle spend. When the application has been idle for several minutes, Azure terminates running replicas; first load after idle takes several seconds (~15–30 seconds) while Azure provisions a container replica. Subsequent requests respond in <1 second.

> [!WARNING]
> **Data Privacy Notice:** Synthetic questions only; free Gemini tier may use prompts to improve Google products per Google's terms of service. **Never submit real Protected Health Information (PHI).**

---

## Execution Modes

The assistant supports both live model inference and zero-credential scripted demonstration:

| Mode | Environment Config | Description | Sidebar Status Banner |
|---|---|---|---|
| **Scripted Demo (Default)** | `LLM_MODE=scripted` (or empty `GEMINI_API_KEY`) | Deterministic, fully offline demonstration using `ScriptedLLM`. Accurately answers the 13 standard demo questions from `hospital_faq.md`, returning a clear fallback message for other inquiries without making network calls. | `SCRIPTED DEMO (no model)` |
| **Live Inference** | `LLM_MODE=live` + `GEMINI_API_KEY=...` | Direct live inference using Gemini (`gemini-3.8-flash`) via `google-genai`, enforcing structured JSON responses via `response_json_schema`. | `LIVE: <model>` |
| **Kill Switch Override** | `LLM_KILL_SWITCH=true` | Emergency operational circuit breaker that immediately diverts all incoming traffic to `ScriptedLLM` without code deployment. | `SCRIPTED DEMO (no model)` |

---

## Architecture & Turn Pipeline

The chatbot implements a strict defence-in-depth pipeline where deterministic Python code controls all safety refusals rather than relying on LLM self-moderation:

```mermaid
flowchart TD
    A["User Input (Streamlit UI)"] --> B["Session Rate Limiter\n(Max 30 turns / 2s min interval)"]
    B --> C["Input Validator\n(Trim & 500 characters cap)"]
    C --> D["PII Redactor\n(Masks email, mobile, 12-digit IDs)"]
    D --> E{"Deterministic Pre-check\n(Emergency & Clinical Regex)"}
    E -- "Emergency Match" --> E1["Fixed Emergency Refusal\n(080-0000-0911 / 112)"]
    E -- "Clinical Match" --> E2["Fixed Clinical Refusal\n(No diagnosis or dosing)"]
    E -- "Safe Input" --> F{"Deterministic Injection Check\n(DAN, overrides, delimiters)"}
    F -- "Injection Detected" --> F1["Fixed Injection Refusal\n(injection_detected flag)"]
    F -- "Clean Input" --> G{"Daily LLM Call Cap\n(200 calls/day UTC midnight)"}
    G -- "Cap Exhausted" --> G1["Friendly Cap Limit Refusal\n(daily_cap_reached flag)"]
    G -- "Cap Available" --> H["Context Builder\n(Last N unblocked turns)"]
    H --> I{"Execution Mode"}
    I -- "LLM_MODE=scripted" --> J1["ScriptedLLM\n(Deterministic offline FAQ answers)"]
    I -- "LLM_MODE=live" --> J2["Gemini API (google-genai)\n(Structured JSON response_json_schema)"]
    J1 --> K["JSON Validation\n(BotReply Schema)"]
    J2 --> K
    K --> L{"Output Guardrails"}
    L -- "Contains dosage (mg, ml, iu)" --> L1["Clinical Refusal\n(output_dose_blocked)"]
    L -- "Ungrounded contact details" --> L2["Front Desk Fallback\n(ungrounded_contact_blocked)"]
    L -- "Grounded FAQ answer" --> M["Structured JSON Logging\n(Allowlisted metadata-only event)"]
    E1 --> M
    E2 --> M
    F1 --> M
    G1 --> M
    L1 --> M
    L2 --> M
    M --> N["Streamlit Response Render\n(Chat UI + Sidebar Token / Cost Metrics)"]
```

---

## Safety Guardrails (Defence-in-Depth)

| Guardrail | Stage | Mechanism | Purpose | Token Cost |
|---|---|---|---|---|
| **Rate Limiter** | Pre-Pipeline | In-memory timestamp & turn tracker | Enforces `MAX_TURNS_PER_SESSION=30` and `MIN_SECONDS_BETWEEN_TURNS=2` | 0 tokens |
| **Input Validation** | Pre-Check | String validation | Rejects empty strings and caps messages at 500 characters | 0 tokens |
| **PII Redaction** | Pre-Check | Regex matching Indian mobile, email, 12-digit IDs | Replaces sensitive identifiers with `[REDACTED]` before model invocation | 0 tokens |
| **Pre-Check Guard** | Pre-Check | Deterministic regex for emergencies & clinical questions | Emergency queries trigger `EMERGENCY_TEXT`; clinical queries trigger `CLINICAL_REFUSAL_TEXT` immediately | 0 tokens |
| **Prompt Injection Guard** | Pre-Check | Regex scanning for DAN, system prompt extraction, delimiter spoofing | Rejects injection attacks before LLM invocation, setting `injection_detected` | 0 tokens |
| **Daily Call Cap** | Pre-LLM | Process-wide atomic counter reset at UTC midnight | Caps daily LLM calls at `DAILY_LLM_CALL_CAP=200` to prevent bill shock | 0 tokens |
| **Structured Output** | Generation | `response_json_schema` via Gemini API | Forces model to return `{category, answer}` JSON adhering to strict Pydantic schema | Model inference |
| **Refusal Text Ownership** | Post-LLM | Python category combiner | Application code decides user-facing refusal text; LLM cannot be manipulated | 0 tokens |
| **Output Dose Guard** | Post-LLM | Regex for dosage numbers (`mg`, `ml`, `mcg`, `iu`) | Blocks accidental dosage outputs in model answers and substitutes clinical refusal | 0 tokens |
| **Output Contact Grounding** | Post-LLM | Contact detail extractor (phone, email, URL) | Verifies every contact against `hospital_faq.md`; substitutes safe front desk fallback if hallucinated | 0 tokens |

---

## Structured JSON Logging

Every conversation turn emits exactly one structured JSON audit log entry on stdout with allowlisted metadata fields only. User input text, redacted text, model generated answers, and system prompt instructions are strictly excluded.

### Real Sample Log Entries (Measured from Running Session)

**1. Answered FAQ Turn (Scripted Demo Mode):**
```json
{"timestamp": "2026-10-27T18:32:18.240685+00:00", "request_id": "req-audit-789", "session_id": "sess-demo-456", "category": "faq", "llm_called": true, "model": "scripted-demo", "input_tokens": 40, "output_tokens": 30, "est_cost_usd": 0.0001425, "latency_ms": 0.74, "guardrail_flags": [], "outcome": "answered"}
```

**2. Blocked Prompt Injection Turn with Redacted PII:**
```json
{"timestamp": "2026-10-27T18:32:25.230987+00:00", "request_id": "req-injection-101", "session_id": "sess-demo-456", "category": "off_topic", "llm_called": false, "model": "gemini-3.8-flash", "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0, "latency_ms": 0.13, "guardrail_flags": ["injection_detected", "pii_redacted"], "outcome": "refused"}
```

---

## Quickstart

### Prerequisites
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Gemini API key from Google AI Studio (optional; scripted demo works without credentials)

### Setup & Run

```bash
# 1. Clone repository
git clone https://github.com/adwitiya-pandey/patient-faq-chatbot.git
cd patient-faq-chatbot

# 2. Install dependencies into virtual environment
uv sync

# 3. Run full test suite offline (117 tests passing, 0 network calls)
uv run pytest -q

# Real output:
# ........................................................................ [ 61%]
# .............................................                            [100%]
# 117 passed in 1.75s

# 4. Run Streamlit web application (Scripted Demo Mode - Keyless)
LLM_MODE=scripted uv run streamlit run app.py

# 5. Run Streamlit web application (Live Gemini Mode)
cp .env.example .env
# Edit .env and supply GEMINI_API_KEY
uv run streamlit run app.py
```

---

## Screenshots

### Application UI & Git Conflict Resolution Proof
![Streamlit App Interface](docs/screenshots/merge-conflict-resolution.png)
*(See [Merge Conflict Walkthrough](docs/EXPLAIN-PLAIN-ENGLISH.md) for full conflict resolution details and visual Git graph).*

---

## Cost Tracking & Economics

The sidebar tracks real-time session token consumption:
- **Input Tokens**: Count of prompt tokens sent to Gemini.
- **Output Tokens**: Count of candidate tokens generated by Gemini.
- **Estimated Cost**: Calculated using configured token rates (`PRICE_INPUT_PER_M=0.75` and `PRICE_OUTPUT_PER_M=3.75` USD per 1M tokens).
- *Note:* Google Gemini free tier bills $0.00; costs are displayed as notional estimates. Blocked turns that hit pre-checks execute offline at zero cost.

---

## Known Limitations

- **Language Support:** Deterministic regex pre-checks and prompt injection scans are tailored for English inquiries only.
- **Observed Regex Misses:** 
  - Symptom paraphrases that avoid exact trigger words (such as *"I feel an unusual burning sensation behind my sternum after climbing stairs"*, avoiding the phrase "chest pain") depend on the model classifier unless explicitly listed in regex patterns.
  - Spaced telephone numbers (e.g. `+91 98765 43210`) are not matched by the contiguous 10-digit mobile regex.
- **Output Guardrail Granularity:** The dosage guard is an expression unit filter (`mg`, `ml`, `mcg`), not an exhaustive biochemical entity extractor.
- **Data Privacy Notice:** When operating on Google's free Gemini tier, prompt data may be reviewed by human reviewers and used to improve Google products per Google terms of service. Users should only enter synthetic patient questions, never real protected health information (PHI).

---

## Repository Layout

```text
patient-faq-chatbot/
├── .dockerignore
├── .editorconfig
├── .env.example
├── .gitattributes
├── .github/
│   ├── agents/
│   │   └── builder.agent.md
│   └── workflows/
│       ├── ci.yml
│       └── publish-image.yml
├── .gitignore
├── .python-version
├── .vscode/
│   └── settings.json
├── AGENTS.md
├── Dockerfile
├── LICENSE
├── README.md
├── SPEC.md
├── TASKS.md
├── app.py
├── data/
│   └── hospital_faq.md
├── docs/
│   ├── DEPLOY.md
│   ├── EXPLAIN-PLAIN-ENGLISH.md
│   ├── decisions.md
│   ├── demo_questions.md
│   ├── observations.md
│   ├── open_questions.md
│   ├── screenshots/
│   │   └── merge-conflict-resolution.png
│   └── sdk_notes.md
├── prompts/
│   └── system_prompt.md
├── pyproject.toml
├── scripts/
│   ├── azure/
│   │   ├── budget.sh
│   │   ├── deploy.sh
│   │   └── teardown.sh
│   ├── live_smoke.py
│   └── smoke_remote.py
├── src/faq_bot/
│   ├── __init__.py
│   ├── chat.py
│   ├── config.py
│   ├── cost.py
│   ├── llm.py
│   ├── logging_setup.py
│   ├── messages.py
│   ├── models.py
│   ├── prompts.py
│   ├── rate_limit.py
│   ├── safety.py
│   └── scripted_llm.py
├── tests/
│   ├── __init__.py
│   ├── fakes.py
│   ├── test_chat.py
│   ├── test_config.py
│   ├── test_cost.py
│   ├── test_grounding.py
│   ├── test_injection.py
│   ├── test_llm.py
│   ├── test_logging.py
│   ├── test_prompt.py
│   ├── test_rate_limit.py
│   ├── test_readme_tree.py
│   ├── test_safety.py
│   ├── test_scripted_llm.py
│   ├── test_security.py
│   ├── test_smoke.py
│   ├── test_smoke_remote.py
│   └── test_ui.py
└── uv.lock
```

For detailed architectural trade-offs, see [Architecture Decisions](docs/decisions.md).
