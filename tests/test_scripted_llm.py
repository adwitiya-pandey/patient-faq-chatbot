"""Tests for ScriptedLLM and scripted demo mode (Step 6)."""

from faq_bot.chat import handle_turn
from faq_bot.config import Config, load_config
from faq_bot.models import Message
from faq_bot.rate_limit import RateLimiter
from faq_bot.scripted_llm import SCRIPTED_DEMO_QA, ScriptedLLM

DEMO_QUESTIONS = [
    "I have severe chest pain and tightness in my chest.",
    "My father is unconscious and not breathing properly.",
    "She took an overdose of sleeping pills and cannot wake up.",
    "Can you diagnose my skin rash and fever?",
    "What dose of paracetamol should I take for my headache?",
    "Should I stop taking my blood pressure medication before my visit?",
    "How do I book an appointment at Northfield Hospital?",
    "Can I reschedule or cancel my appointment without a fee?",
    "Which insurance companies do you accept for cashless admission?",
    "How early should I arrive at the hospital before scheduled surgery?",
    "Is the hospital pharmacy open 24 hours?",
    "Do I need a prescription to refill my medicines at the pharmacy?",
    "I feel an unusual burning sensation behind my sternum after climbing stairs, should I rest or get checked?",
]


def test_scripted_llm_answers_all_13_demo_questions():
    """Verify ScriptedLLM handles all 13 demo questions from docs/demo_questions.md."""
    llm = ScriptedLLM()
    assert len(SCRIPTED_DEMO_QA) == 13

    for question in DEMO_QUESTIONS:
        result = llm.generate_json(
            system_prompt="system",
            contents=[Message(role="user", text=question)],
        )
        assert result.text, f"Empty response for question: {question}"
        assert '"category"' in result.text
        assert '"answer"' in result.text


def test_scripted_llm_fallback_for_unknown_question():
    """Verify unknown questions receive the default scripted demo answer."""
    llm = ScriptedLLM()
    result = llm.generate_json(
        system_prompt="system",
        contents=[Message(role="user", text="Can I bring my pet dog to the clinic?")],
    )
    assert "This is a scripted demo answer." in result.text


def test_handle_turn_in_scripted_mode_without_credentials():
    """Verify handle_turn operates completely offline when llm_mode='scripted'."""
    cfg = Config(gemini_api_key="", llm_mode="scripted")
    limiter = RateLimiter(time_fn=lambda: 1000.0)

    # 1. Test scripted FAQ question
    res_faq = handle_turn(
        history=[],
        text="How do I book an appointment at Northfield Hospital?",
        config=cfg,
        rate_limiter=limiter,
    )
    assert res_faq.category == "faq"
    assert res_faq.blocked is False
    assert "080-0000-0100" in res_faq.text
    assert "portal.northfield.example" in res_faq.text

    # 2. Test unknown question receives scripted fallback
    limiter.reset()
    res_unknown = handle_turn(
        history=[],
        text="What are cafeteria opening times?",
        config=cfg,
        rate_limiter=limiter,
    )
    assert res_unknown.category == "faq"
    assert res_unknown.blocked is False
    assert "This is a scripted demo answer." in res_unknown.text


def test_kill_switch_triggers_scripted_mode():
    """Verify llm_kill_switch=True diverts requests to ScriptedLLM."""
    cfg = Config(
        gemini_api_key="mock-key",
        llm_mode="live",
        llm_kill_switch=True,
    )
    limiter = RateLimiter(time_fn=lambda: 2000.0)

    res = handle_turn(
        history=[],
        text="Is the hospital pharmacy open 24 hours?",
        config=cfg,
        rate_limiter=limiter,
    )
    assert res.category == "faq"
    assert "24 hours daily" in res.text


def test_config_modes():
    """Verify load_config parses live and scripted modes."""
    cfg_live = load_config(env={"GEMINI_API_KEY": "dummy", "LLM_MODE": "live"})
    assert cfg_live.llm_mode == "live"

    cfg_scripted = load_config(env={"LLM_MODE": "scripted"})
    assert cfg_scripted.llm_mode == "scripted"
    assert cfg_scripted.gemini_api_key == ""
