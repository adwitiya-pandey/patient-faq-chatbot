# AGENTS.md

> **AUTONOMOUS END-TO-END EXECUTION RULE (SINGLE-CHAT WORKFLOW)**:
> Execute **all tasks in `TASKS.md` back-to-back from `T0`/`H0` through `v0.1.0` GitHub push** in a single continuous run.
> - **Do NOT stop after individual tasks** to wait for human PR merges. Commit each task cleanly with Conventional Commits (`Refs: <TaskID>`), merge branches automatically, update `PROGRESS.md`, and continue straight to the next task.
> - **Write 100% of the code yourself** (including `queries.py`, `graph.py`, `policy.py`, `approvals.py`, `sqlsafe.py`, and the `H9` merge conflict).
> - **API Keys**: Use `GEMINI_API_KEY` from the project's `.env` file for live Gemini steps. Never require `ANTHROPIC_API_KEY` or `LANGSMITH_API_KEY`.


Read SPEC.md (the contract), the TASKS.md task you were given, and the SPEC sections that task cites, before touching code. This file holds only what is not obvious from the code.

## What this is
A patient FAQ chatbot for a fictional hospital built in raw Python using the official Google GenAI SDK (`google-genai`, Gemini free/Pro tier) plus Streamlit and `pytest`. No frameworks, no database, no Anthropic SDK (100% Google GenAI SDK). Python 3.13, `uv`.

## Environment and commands
- The owner works in WSL2 Ubuntu (repo under `~/projects`, never under `/mnt/c` or `/mnt/d`) and sometimes opens it from Windows. CI runs Linux. Use `pathlib`; no shell-specific paths. Tests must pass on Windows and Linux, offline, with no API key set. Line endings are LF.
- Install: `uv sync`
- Check: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- Run the app: `uv run streamlit run app.py` (needs a real key; the owner does this, task H7)
- Run each task's own acceptance command from TASKS.md before committing.
- Run only the commands above, the task's own commands, and `git`/`gh` for the task's branch and PR. Ask before anything else.

## Gotchas that will bite you
1. **Provider SDK only in `llm.py`**. Use `from google import genai` and `from google.genai import types`; `genai.Client(api_key=...)`; `client.models.generate_content(...)`. An AST test in `test_security.py` bans `langchain*`, `llama_index*`, `openai`, and `anthropic` across the entire repository.
2. **Do not invent SDK details.** `docs/sdk_notes.md` holds what was verified on 18 Oct 2026 (google-genai 2.31.0: config fields, `Content`/`Part`, usage field names, `APIError`). Re-run its probe against the installed versions before coding against it and correct the file if anything differs. If a pattern is not documented, say so there and use the simplest documented one.
3. **Refusal text comes from `messages.py`, never from the model.** The model returns `{category, answer}`; Python decides what the user sees for every category except `faq`.
4. **Pre-check before the LLM.** Emergency and clinical regex run first. When they hit, the LLM is not called. Tests assert the fake LLM was called zero times.
5. **Streamlit reruns the whole script on every click.** State lives only in `st.session_state`. Never keep history in a module-level variable.
6. **Never log user or bot text.** Log lines hold metadata only (SPEC 15, S4). Never print the API key, even partially.
7. **Regex:** use `re.fullmatch` where you mean the whole string, `[0-9]` rather than `\d`, and keep the validated starter patterns in SPEC 17. Add failing test cases before changing a pattern. Never loosen a pattern to make a test pass.
8. **Tests never touch the network.** Use `tests/fakes.py`. A test that needs a key is a bug.
9. **Cost is an estimate** (tokens x configured price); the free tier bills zero. Label it "estimate".

## Never
- Execute the branching and deliberate merge-conflict exercise (`H9`) automatically: create `feature/prompt-friendly` and `feature/prompt-concise` from `dev`, edit rule 7 of `prompts/system_prompt.md` differently on each branch, merge the first into `dev`, trigger the real Git conflict on the second merge, resolve it cleanly into a non-fast-forward merge commit visible in `git log --graph --oneline`, and document the conflict resolution in `docs/EXPLAIN-PLAIN-ENGLISH.md`.
- Merge `feature/*` branches into `dev` and `dev` into `main` automatically as part of the end-to-end run.
- Never print or commit `.env` (keep `.env` in `.gitignore`; load it automatically via `python-dotenv` / `pydantic-settings`), real keys or `*.db` files. Create `.env.example` only, with dummy values. The owner stores `GEMINI_API_KEY` in the project's local `.env` file (gitignored, loaded via `python-dotenv`). Never print or commit `.env`.
- Keep unit tests (`pytest`) 100% offline using `FakeLLM`. In `H7`, use `GEMINI_API_KEY` from the project's `.env` file to run the live smoke test against `docs/demo_questions.md` and record results in `docs/observations.md`.
- Never add a dependency that is not in SPEC section 18 without asking. Never add LangChain, LlamaIndex, tenacity, or any provider SDK other than the ones SPEC 12 and 23 allow.
- Never change SPEC.md, a fixed message string, a category name or a security requirement to make a test pass. Fix the code, or stop and ask.
- Never skip, delete or weaken a safety test.
- Never make the bot answer a clinical question, even "just general information". Over-refusing is the accepted failure mode.

## Work style: autonomous, with a short list of reasons to stop
- One task per branch (`feature/h3-safety`), execute all tasks in order continuously, updating PROGRESS.md after each task. Your first message: the task ID, the files you will touch, the tests you will write first, the acceptance command. Keep it short, then proceed.
- Tests first for H3 (safety) and H4 (chat, llm): write the failing tables from the SPEC, watch them fail, then implement.
- Commits follow Conventional Commits: `type(scope): imperative summary`, at most 72 characters, no task ID in the subject. Types: `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`. Put `Refs: H3` as a trailer. Example: `feat(safety): add emergency and clinical pre-check`.
- Open a pull request into `dev` with a conventional title and stop. Do not ask permission for routine work.
- Two-step git in any instructions you write for the owner: `git branch <name>` then `git switch <name>`; never `git checkout -b`.
- Facts only from official docs (Gemini API, Streamlit, pytest, uv, Pydantic) and the installed packages. No blog posts.
- Execute H0 through H10 continuously from start to finish (skip H11 and H12 — this project uses ONLY `google-genai`).
- Model choice (Copilot): Gemini 3.8 Flash High (Antigravity) / Copilot Auto for every task. H3 and H4 are where subtle mistakes hide: re-read your diff against the SPEC before opening the PR.
- Keep replies short: what changed, the last lines of the acceptance command, what the owner should read.

**Stop and ask the owner before:** adding or upgrading a dependency; changing SPEC.md or a fixed message; deleting or renaming files outside the task's scope; any network access other than package installs and official docs; touching `.github/workflows/` beyond what the task says; anything that makes a safety layer weaker.

If SPEC is ambiguous, choose the safer reading (more refusal, less logging), record the question in `docs/open_questions.md`, and continue.

## Definition of done for every task
The acceptance command passes; ruff is clean; new behaviour has a test; `docs/decisions.md` is updated if a decision changed; the code reads clearly to a beginner (short functions, a comment saying why, no cleverness). End the PR body with three lines: what changed, how it was verified, what the owner should read to understand it.

## Harness
This file is read by VS Code Copilot (setting `chat.useAgentsMdFile`) and by Antigravity (1.20.5 or later). If it is not in your context, say so before doing anything else. Keep this file under 12,000 characters (Antigravity's per-rules-file limit).
