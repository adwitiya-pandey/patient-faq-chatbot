"""Smoke test for Streamlit UI using AppTest without a browser."""

import os
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from faq_bot.messages import DISCLAIMER

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_ui_renders_disclaimer():
    """Verify app renders disclaimer caption and title using AppTest."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-test-key"}):
        at = AppTest.from_file(APP_PATH, default_timeout=5).run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        assert any(DISCLAIMER in c for c in captions)
        assert len(at.title) == 1
        assert "Northfield Multispecialty Hospital Patient FAQ" in at.title[0].value


def test_ui_missing_key_shows_error_no_traceback():
    """When GEMINI_API_KEY is unset, app shows error banner instead of traceback."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        at = AppTest.from_file(APP_PATH, default_timeout=5).run()
        # Verify no unhandled exception traceback
        assert not at.exception
        assert len(at.error) >= 1
        assert "Please set GEMINI_API_KEY" in at.error[0].value
