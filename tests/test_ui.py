"""Smoke test for Streamlit UI using AppTest without a browser (Step 6)."""

import os
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from faq_bot.messages import DISCLAIMER

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_ui_renders_disclaimer_and_live_banner():
    """Verify app renders disclaimer, title, and live model banner in live mode."""
    with patch.dict(
        os.environ, {"GEMINI_API_KEY": "dummy-test-key", "LLM_MODE": "live"}
    ):
        at = AppTest.from_file(APP_PATH, default_timeout=5).run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        assert any(DISCLAIMER in c for c in captions)
        assert len(at.title) == 1
        assert "Northfield Multispecialty Hospital Patient FAQ" in at.title[0].value
        success_msgs = [s.value for s in at.sidebar.success]
        assert any("LIVE: gemini-3.8-flash" in s for s in success_msgs)


def test_ui_renders_scripted_demo_banner():
    """Verify app renders SCRIPTED DEMO banner when in scripted mode."""
    with patch.dict(
        os.environ, {"LLM_MODE": "scripted", "GEMINI_API_KEY": ""}, clear=False
    ):
        at = AppTest.from_file(APP_PATH, default_timeout=5).run()
        assert not at.exception
        warning_msgs = [w.value for w in at.sidebar.warning]
        assert any("SCRIPTED DEMO (no model)" in w for w in warning_msgs)


def test_ui_missing_key_in_live_mode_shows_error():
    """When LLM_MODE is live but GEMINI_API_KEY is unset, app shows error banner instead of traceback."""
    with patch.dict(
        os.environ, {"GEMINI_API_KEY": "", "LLM_MODE": "live"}, clear=False
    ):
        at = AppTest.from_file(APP_PATH, default_timeout=5).run()
        assert not at.exception
        assert len(at.error) >= 1
        assert "Please set GEMINI_API_KEY" in at.error[0].value
