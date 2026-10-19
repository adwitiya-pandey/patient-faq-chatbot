"""Tests for prompt loading and template formatting."""

from faq_bot.prompts import build_system_prompt, get_project_root


def test_system_prompt_file_has_at_least_30_lines():
    """Ensure the system prompt template file has at least 30 lines."""
    template_path = get_project_root() / "prompts" / "system_prompt.md"
    assert template_path.is_file()
    lines = template_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 30, f"Expected >= 30 lines, got {len(lines)}"


def test_build_system_prompt_fills_placeholders():
    """Ensure placeholders {hospital_name} and {faq_text} are substituted."""
    hospital = "Test City Hospital"
    prompt = build_system_prompt(hospital_name=hospital)

    # Placeholders should be gone
    assert "{hospital_name}" not in prompt
    assert "{faq_text}" not in prompt

    # Hospital name should be present
    assert hospital in prompt

    # FAQ facts must be present
    assert "080-0000-0100" in prompt
    assert "care@northfield.example" in prompt
    assert "portal.northfield.example" in prompt

    # Specific required safety rules must be present
    # Rule never diagnose
    assert "diagnose" in prompt.lower()
    # Rule treat user input as data
    assert "data" in prompt.lower()
    assert "untrusted" in prompt.lower() or "treat" in prompt.lower()
