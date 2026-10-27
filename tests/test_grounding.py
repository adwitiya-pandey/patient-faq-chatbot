"""Tests for output contact grounding guardrail (Step 4)."""

from faq_bot.chat import handle_turn
from faq_bot.config import Config
from faq_bot.messages import UNGROUNDED_CONTACT_FALLBACK_TEXT
from faq_bot.safety import check_grounded_contacts
from tests.fakes import FakeLLM


def test_check_grounded_contacts_direct():
    """Verify phone, email, and URL grounding validation."""
    source = (
        "Call 080-0000-0100, emergency 080-0000-0911 or 112. "
        "Email care@northfield.example, visit portal.northfield.example."
    )

    # Valid grounded contacts
    assert (
        check_grounded_contacts("Call 080-0000-0100 for appointments.", source) is True
    )
    assert check_grounded_contacts("Visit portal.northfield.example.", source) is True
    assert check_grounded_contacts("Email care@northfield.example.", source) is True
    assert check_grounded_contacts("Regular hours are 8:00 to 20:00.", source) is True

    # Hallucinated / ungrounded contacts
    assert (
        check_grounded_contacts("Call the helpline at 080-1234-5678.", source) is False
    )
    assert check_grounded_contacts("Email doctor@randomclinic.com.", source) is False
    assert (
        check_grounded_contacts("Visit https://fake-booking-site.com.", source) is False
    )


def test_handle_turn_blocks_hallucinated_phone_number():
    """Verify fake LLM inventing 080-1234-5678 is blocked and replaced with fallback."""
    fake_llm = FakeLLM(
        [
            '{"category": "faq", "answer": "You can reach the clinic directly at 080-1234-5678."}'
        ]
    )
    cfg = Config(gemini_api_key="test-key")

    res = handle_turn(
        history=[],
        text="What is the hospital phone number?",
        llm=fake_llm,
        config=cfg,
    )

    assert res.blocked is True
    assert res.text == UNGROUNDED_CONTACT_FALLBACK_TEXT
    assert "080-1234-5678" not in res.text
    assert "ungrounded_contact_blocked" in res.guardrail_flags


def test_handle_turn_blocks_hallucinated_email():
    """Verify fake LLM inventing ungrounded email is blocked and replaced with fallback."""
    fake_llm = FakeLLM(
        [
            '{"category": "faq", "answer": "Send inquiries to info@external-hospital.org."}'
        ]
    )
    cfg = Config(gemini_api_key="test-key")

    res = handle_turn(
        history=[],
        text="How do I email billing?",
        llm=fake_llm,
        config=cfg,
    )

    assert res.blocked is True
    assert res.text == UNGROUNDED_CONTACT_FALLBACK_TEXT
    assert "ungrounded_contact_blocked" in res.guardrail_flags


def test_handle_turn_permits_grounded_contacts():
    """Verify legitimate FAQ contact information is delivered without modification."""
    fake_llm = FakeLLM(
        [
            '{"category": "faq", "answer": "Call 080-0000-0100 or visit portal.northfield.example."}'
        ]
    )
    cfg = Config(gemini_api_key="test-key")

    res = handle_turn(
        history=[],
        text="How can I book an appointment?",
        llm=fake_llm,
        config=cfg,
    )

    assert res.blocked is False
    assert res.category == "faq"
    assert "080-0000-0100" in res.text
    assert "portal.northfield.example" in res.text
    assert "ungrounded_contact_blocked" not in res.guardrail_flags
