"""Security and privacy requirement tests (SPEC 15 and AST import ban)."""

import ast
import logging
from pathlib import Path

import pytest

from faq_bot.chat import handle_turn
from faq_bot.config import Config, load_config
from faq_bot.messages import DISCLAIMER
from faq_bot.safety import output_guard, validate_input
from tests.fakes import FakeLLM


def get_project_root() -> Path:
    """Return project root directory."""
    return Path(__file__).resolve().parent.parent


def test_gitignore_has_env():
    """S1: .gitignore must contain .env and prevent committing secrets."""
    gitignore_path = get_project_root() / ".gitignore"
    assert gitignore_path.is_file()
    lines = [
        line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()
    ]
    assert ".env" in lines
    assert ".streamlit/secrets.toml" in lines


def test_env_example_has_no_real_key():
    """S1: .env.example must not contain real keys or Google API key prefixes."""
    env_example = get_project_root() / ".env.example"
    assert env_example.is_file()
    content = env_example.read_text(encoding="utf-8")
    assert ("AI" + "za") not in content
    # Ensure key line is dummy
    assert "GEMINI_API_KEY=your-key-here" in content


def test_config_error_does_not_echo_key():
    """S2: Invalid or missing key error messages must never echo key values."""
    secret_key = "SecretLeakCheckValue123"
    with pytest.raises(ValueError) as exc_info:
        # Pass a dict where key is empty to trigger error
        load_config(env={"GEMINI_API_KEY": ""})
    assert secret_key not in str(exc_info.value)

    cfg = Config(gemini_api_key=secret_key)
    assert secret_key not in repr(cfg)


def test_pii_redacted_before_llm():
    """S3: PII is replaced with [REDACTED] before reaching the LLM."""
    llm = FakeLLM(['{"category": "faq", "answer": "I have received your inquiry."}'])
    cfg = Config(gemini_api_key="test-key")
    sensitive_input = (
        "Contact patient at patient@example.com or 9876543210 with id 1234 5678 9012"
    )
    res = handle_turn(history=[], text=sensitive_input, llm=llm, config=cfg)

    assert res.pii_redacted is True
    assert len(llm.calls) == 1
    sent_prompt = llm.calls[0]["contents"][0].text
    assert "patient@example.com" not in sent_prompt
    assert "9876543210" not in sent_prompt
    assert "1234 5678 9012" not in sent_prompt
    assert "[REDACTED]" in sent_prompt


def test_log_line_has_no_text(caplog: pytest.LogCaptureFixture):
    """S4: Log records must hold metadata only and NEVER log user or bot text."""
    secret_user_text = "PrivateLogCheckQuestion"
    fake_bot_reply = "ConfidentialAnswerText"

    llm = FakeLLM([f'{{"category": "faq", "answer": "{fake_bot_reply}"}}'])
    cfg = Config(gemini_api_key="test-key")

    with caplog.at_level(logging.INFO, logger="faq_bot.chat"):
        handle_turn(history=[], text=secret_user_text, llm=llm, config=cfg)

    # Check all captured log messages
    chat_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "faq_bot.chat"
    ]
    assert len(chat_logs) >= 1
    for log_msg in chat_logs:
        assert secret_user_text not in log_msg
        assert fake_bot_reply not in log_msg
        assert "Turn completed:" in log_msg
        assert "category=" in log_msg
        assert "model=" in log_msg


def test_no_files_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """S5: Turn processing does not create or persist conversation files on disk."""
    monkeypatch.chdir(tmp_path)
    initial_files = set(tmp_path.rglob("*"))

    llm = FakeLLM(['{"category": "faq", "answer": "The hospital is open."}'])
    cfg = Config(gemini_api_key="test-key")
    handle_turn(history=[], text="What are the hours?", llm=llm, config=cfg)

    current_files = set(tmp_path.rglob("*"))
    assert current_files == initial_files


def test_emergency_skips_llm():
    """S6: Emergency pre-check executes before LLM and makes zero LLM calls."""
    llm = FakeLLM()
    cfg = Config(gemini_api_key="test-key")
    handle_turn(
        history=[],
        text="I have chest tightness and cannot breathe",
        llm=llm,
        config=cfg,
    )
    assert len(llm.calls) == 0


def test_clinical_skips_llm():
    """S6: Clinical pre-check executes before LLM and makes zero LLM calls."""
    llm = FakeLLM()
    cfg = Config(gemini_api_key="test-key")
    handle_turn(
        history=[], text="What is the dosage of amoxicillin?", llm=llm, config=cfg
    )
    assert len(llm.calls) == 0


def test_output_guard_blocks_dose():
    """S7: Output guard blocks answers containing numerical doses."""
    assert output_guard("Take 10 mg at night") is True
    assert output_guard("Give 5 ml syrup") is True
    assert output_guard("Arrive 2 hours early") is False


def test_input_validation():
    """S8: Input capped at 500 characters and empty input rejected."""
    _clean, empty_err = validate_input("   ", max_chars=500)
    assert empty_err == "empty"

    _long_clean, long_err = validate_input("x" * 501, max_chars=500)
    assert long_err == "too_long"


def test_disclaimer_constant_exists():
    """S9: Disclaimer string constant exists and warns patient."""
    assert len(DISCLAIMER) > 20
    assert "not a medical professional" in DISCLAIMER.lower()


def test_ast_import_ban():
    """Constraint check: Walk src/ and app.py with AST.

    Disallow langchain*, llama_index*, openai, and anthropic across all files.
    Disallow google / google.genai imports in any module other than llm.py.
    """
    root = get_project_root()
    files_to_check: list[Path] = list((root / "src").rglob("*.py"))
    app_file = root / "app.py"
    if app_file.is_file():
        files_to_check.append(app_file)

    banned_anywhere = {"langchain", "llama_index", "openai", "anthropic"}

    for py_file in files_to_check:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        rel_path = py_file.relative_to(root).as_posix()
        is_llm_module = rel_path == "src/faq_bot/llm.py"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    # Check banned frameworks everywhere
                    for banned in banned_anywhere:
                        assert not top_pkg.startswith(banned), (
                            f"Banned package '{alias.name}' imported in {rel_path}"
                        )
                    # Check google imports only in llm.py
                    if top_pkg == "google" and not is_llm_module:
                        pytest.fail(f"google SDK imported outside llm.py in {rel_path}")

            elif isinstance(node, ast.ImportFrom) and node.module:
                top_pkg = node.module.split(".")[0]
                for banned in banned_anywhere:
                    assert not top_pkg.startswith(banned), (
                        f"Banned package '{node.module}' imported in {rel_path}"
                    )
                if top_pkg == "google" and not is_llm_module:
                    pytest.fail(f"google SDK imported outside llm.py in {rel_path}")
