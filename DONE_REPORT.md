# Done Report: Patient FAQ Chatbot Standards Upgrade

**Branch:** `chore/audit-standards-upgrade`  
**Remote Tracking:** `origin/chore/audit-standards-upgrade`  
**Base:** `main` (commit `3f71c12`)  
**CI/Test Status:** 117 passed in 3.10s (100% offline, 0 network calls)  
**Ruff Status:** All checks passed, 44 files already formatted  

---

## 1. Steps Completed

| Step | Scope | Commit | Key Deliverables |
|---|---|---|---|
| **Step 1** | Live Call Diagnosis & Modular Config | `67e3ced` | Created `scripts/live_smoke.py`, diagnosed free-tier 20 requests/day quota (`429 RESOURCE_EXHAUSTED`) and transient `503 UNAVAILABLE` spikes on `gemini-3.8-flash`. Confirmed `response_json_schema` supports OpenAPI 3.1 schemas with forbidden additional properties. Modularized `build_generate_content_config` in `src/faq_bot/llm.py` and added unit test. Documented root cause in `docs/decisions.md` (D13). |
| **Step 2** | Structured JSON Logging | `0553313` | Created `src/faq_bot/logging_setup.py` implementing stdlib `JsonFormatter` with 12 allowlisted fields (`timestamp`, `request_id`, `session_id`, `category`, `llm_called`, `model`, `input_tokens`, `output_tokens`, `est_cost_usd`, `latency_ms`, `guardrail_flags`, `outcome`). Configured once at startup in `app.py`. Added comprehensive tests in `tests/test_logging.py` asserting fields present and forbidden content (user prompt, answers, PII) strictly absent. |
| **Step 3** | Deterministic Injection Guard | `106e55c` | Added `injection_check(text)` to `src/faq_bot/safety.py` covering instruction disregard/overrides, system prompt leakage, DAN/developer mode, roleplay hijacking, base64 payloads, and delimiter spoofing (`</system>`). Added `tests/test_injection.py` validating 14 attack strings blocked (100%) and 9 benign customer queries permitted (0.0% false positives, including "Please ignore my earlier message, I meant Tuesday"). Documented results in `docs/observations.md`. |
| **Step 4** | Output Grounding Guard | `560e880` | Implemented `check_grounded_contacts(answer)` in `src/faq_bot/safety.py` extracting phone numbers, emails, and URLs and validating against `hospital_faq.md` and emergency constants. Replaces ungrounded answers with safe front-desk fallback ("Please call the front desk at 080-0000-0100.") and sets `ungrounded_contact_blocked`. Added tests in `tests/test_grounding.py` verifying fake LLM inventing `080-1234-5678` is blocked. |
| **Step 5** | Rate Limit & Daily Call Cap | `fefff8e` | Added configuration in `src/faq_bot/config.py` and `.env.example` for `MAX_TURNS_PER_SESSION=30`, `MIN_SECONDS_BETWEEN_TURNS=2`, `DAILY_LLM_CALL_CAP=200`, and `LLM_KILL_SWITCH=false`. Created `src/faq_bot/rate_limit.py` tracking session turn intervals and process-wide daily call counter resetting at UTC midnight. Added `tests/test_rate_limit.py` using fake clock and date doubles. |
| **Step 6** | Scripted Demo Mode | `fd66a7d` | Created `src/faq_bot/scripted_llm.py` providing `ScriptedLLM`, answering the 13 demo questions from `docs/demo_questions.md` with honest grounded FAQ facts and returning fallback for unknown questions. Configured `LLM_MODE=scripted|live` (defaults to `scripted` when key is omitted). Added sidebar status banner `SCRIPTED DEMO (no model)` or `LIVE: <model>` in `app.py`. Added tests in `tests/test_scripted_llm.py` and updated `tests/test_ui.py`. |
| **Step 7** | README & Tree Test | `15ab0d1` | Updated `README.md` with: run modes table, complete guardrail table, real sample log lines, expanded known limitations (English regex boundaries, cardiac paraphrase misses, Google free-tier prompt data use terms notice), and strict Mermaid architecture flowchart. Regenerated repository tree from `git ls-files` and created `tests/test_readme_tree.py`. |

---

## 2. Real Execution Log Samples (First 3 Turns in Each Mode)

### A. Scripted Demo Mode (`LLM_MODE=scripted`)
```json
{"timestamp": "2026-10-27T18:34:34.997953+00:00", "request_id": "bcb30f48-d2d0-4ee3-ba61-96b9e835909c", "session_id": "scripted-session-1", "category": "faq", "llm_called": true, "model": "scripted-demo", "input_tokens": 40, "output_tokens": 30, "est_cost_usd": 0.0001425, "latency_ms": 1.02, "guardrail_flags": [], "outcome": "answered"}
{"timestamp": "2026-10-27T18:34:34.998894+00:00", "request_id": "7e007050-bc3d-4784-8dcf-6bbc6c96ba38", "session_id": "scripted-session-1", "category": "faq", "llm_called": true, "model": "scripted-demo", "input_tokens": 40, "output_tokens": 30, "est_cost_usd": 0.0001425, "latency_ms": 0.66, "guardrail_flags": [], "outcome": "answered"}
{"timestamp": "2026-10-27T18:34:34.999201+00:00", "request_id": "84edb6ca-e334-4778-865f-1b7bae3c45b9", "session_id": "scripted-session-1", "category": "emergency", "llm_called": false, "model": "gemini-3.8-flash", "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0, "latency_ms": 0.14, "guardrail_flags": ["emergency_precheck"], "outcome": "refused"}
```

### B. Live Mode (`LLM_MODE=live`)
```json
{"timestamp": "2026-10-27T18:34:43.216277+00:00", "request_id": "d4697a56-c238-4f21-b265-222dbbeee26c", "session_id": "live-session-1", "category": "emergency", "llm_called": false, "model": "gemini-3.8-flash", "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0, "latency_ms": 0.08, "guardrail_flags": ["emergency_precheck"], "outcome": "refused"}
{"timestamp": "2026-10-27T18:34:43.216569+00:00", "request_id": "0db2fedd-d8e7-476a-b384-3d3c87c0664d", "session_id": "live-session-1", "category": "clinical_advice", "llm_called": false, "model": "gemini-3.8-flash", "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0, "latency_ms": 0.09, "guardrail_flags": ["clinical_precheck"], "outcome": "refused"}
{"timestamp": "2026-10-27T18:34:43.216782+00:00", "request_id": "ae4194c0-9b96-463f-9bd0-d0f35bf56757", "session_id": "live-session-1", "category": "off_topic", "llm_called": false, "model": "gemini-3.8-flash", "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0, "latency_ms": 0.09, "guardrail_flags": ["injection_detected"], "outcome": "refused"}
```

---

## 3. Test & Verification Command Metrics

- `uv run ruff check .` -> Pass (0 lint violations across all modules)
- `uv run ruff format --check .` -> Pass (44 files already formatted)
- `uv run pytest -q` -> Pass (**117 passed in 3.10s**, 0 failed, 0 skipped, 0 network calls)

---

## 4. Files Modified and Created

### Created
1. `scripts/live_smoke.py`
2. `src/faq_bot/logging_setup.py`
3. `src/faq_bot/rate_limit.py`
4. `src/faq_bot/scripted_llm.py`
5. `tests/test_logging.py`
6. `tests/test_injection.py`
7. `tests/test_grounding.py`
8. `tests/test_rate_limit.py`
9. `tests/test_scripted_llm.py`
10. `tests/test_readme_tree.py`
11. `DONE_REPORT.md`

### Modified
1. `app.py`
2. `.env.example`
3. `README.md`
4. `docs/decisions.md`
5. `docs/observations.md`
6. `src/faq_bot/chat.py`
7. `src/faq_bot/config.py`
8. `src/faq_bot/llm.py`
9. `src/faq_bot/messages.py`
10. `src/faq_bot/models.py`
11. `src/faq_bot/safety.py`
12. `tests/test_config.py`
13. `tests/test_llm.py`
14. `tests/test_security.py`
15. `tests/test_ui.py`

---

## 5. Items Skipped and Decision Log

- **Skipped:** None. All 7 steps and acceptance criteria completed.
- **Decision D13 (for review):**
  - Live Gemini probing identified that `gemini-3.8-flash` on the free tier is capped at 20 requests/day per project (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), returning `429 RESOURCE_EXHAUSTED` when depleted, alongside transient `503 UNAVAILABLE` spikes under load.
  - Legacy `response_schema` raises 400 when Pydantic models use `extra="forbid"` (`additionalProperties: false`). Using `response_json_schema` natively supports OpenAPI 3.1 schemas.
  - Keyless scripted demo mode (`LLM_MODE=scripted`) ensures full portfolio utility without requiring active credentials or depleting free-tier quotas.
