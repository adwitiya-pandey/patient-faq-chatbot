# Architecture and Technical Decisions

This document records the 12 core architecture and technical decisions made for the Northfield Hospital Patient FAQ Chatbot, detailing the rationale and trade-offs for each.

| ID | Decision | Why | What We Gave Up |
|---|---|---|---|
| **D1** | **Gemini via `google-genai` SDK exclusively** | Provides a generous free tier for development; the project owner uses Google AI Pro / Developer access exclusively without paid Anthropic access. | The curriculum's Anthropic default; the swap point is isolated in `src/faq_bot/llm.py`. |
| **D2** | **Classify-then-answer with structured JSON** | Python, not the model, owns the refusal text for emergencies, clinical inquiries, and off-topic questions. An adversarial prompt cannot trick the model into prescribing or diagnosing. | A single unstructured string response; requires JSON parsing and Pydantic schema validation. |
| **D3** | **Pre-check regex before calling the LLM** | Deterministic, zero-latency, zero-cost safety layer. Critical emergencies are dispatched immediately without network dependency. | Misses creative rewordings; slightly over-blocks some safe queries (e.g. asking about "interaction" in a non-medical sense). |
| **D4** | **Three-layer defence-in-depth (regex, category, output guard)** | Any single safety layer is susceptible to edge cases or failure modes. Layering guarantees multi-stage mitigation. | Slightly more code and maintenance across three distinct modules. |
| **D5** | **FAQ facts embedded in system prompt, no RAG** | Seed hospital FAQ is under 60 lines and easily fits within Gemini's large context window. | Does not scale to thousands of document pages without moving to vector embeddings. |
| **D6** | **Redact PII before LLM, store nothing to disk** | Healthcare compliance and privacy: user email, Indian mobile numbers, and 12-digit IDs are masked to `[REDACTED]`. | Cannot resume multi-day sessions or personalize patient records. |
| **D7** | **Blocked turns excluded from model context history** | Prevents jailbreak attempts, adversarial tokens, or emergency discussions from persisting into subsequent model context windows. | Model cannot refer back to why an earlier question was refused. |
| **D8** | **Hand-written retry with exponential backoff** | Teaches explicit retry mechanics with 1s, 2s, 4s backoff without adding heavyweight third-party packages. | Pre-built features provided by libraries like `tenacity`. |
| **D9** | **Domain logic in `src/`, thin Streamlit `app.py`** | Allows comprehensive testing of all business logic, turn pipelines, and safety layers without running Streamlit or a browser. | Single-file script simplicity suggested in initial prototypes. |
| **D10** | **Token pricing in configuration** | API pricing models change over time; separating pricing into `.env` ensures code remains unchanged. | Requires managing configuration environment variables. |
| **D11** | **Streamlit rather than Gradio** | Clean session state management (`st.session_state`) for conversation history and running cost metrics. | Custom chat UI styling requires more custom CSS than pre-styled alternatives. |
| **D12** | **Deliberate Git merge conflict creation and resolution (`H9`)** | Provides authentic, demonstrable Git graph branching and conflict resolution evidence documented in plain English. | A simple fast-forward Git history. |
