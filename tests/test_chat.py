"""Tests for chat turn pipeline and conversation orchestration."""

from faq_bot.chat import handle_turn
from faq_bot.config import Config
from faq_bot.messages import (
    CLINICAL_REFUSAL_TEXT,
    EMERGENCY_TEXT,
    FALLBACK_TEXT,
    OFF_TOPIC_TEXT,
)
from tests.fakes import FakeLLM


def test_faq_happy_path():
    """Valid FAQ query returns model answer and is not blocked."""
    llm = FakeLLM(
        ['{"category": "faq", "answer": "The pharmacy is on the ground floor."}']
    )
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(history=[], text="Where is the pharmacy?", llm=llm, config=cfg)

    assert res.category == "faq"
    assert res.blocked is False
    assert res.text == "The pharmacy is on the ground floor."
    assert len(llm.calls) == 1


def test_emergency_skips_llm():
    """Emergency precheck blocks immediately and does NOT call LLM."""
    llm = FakeLLM()
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(history=[], text="I have severe chest pain", llm=llm, config=cfg)

    assert res.category == "emergency"
    assert res.blocked is True
    assert res.text == EMERGENCY_TEXT
    assert len(llm.calls) == 0


def test_clinical_skips_llm():
    """Clinical advice precheck blocks immediately and does NOT call LLM."""
    llm = FakeLLM()
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="What dose of paracetamol should I take?", llm=llm, config=cfg
    )

    assert res.category == "clinical_advice"
    assert res.blocked is True
    assert res.text == CLINICAL_REFUSAL_TEXT
    assert len(llm.calls) == 0


def test_model_detects_clinical_when_regex_misses():
    """When regex misses clinical question, model classification triggers fixed refusal."""
    # A paraphrased clinical inquiry that slipped past regex precheck
    llm = FakeLLM(
        [
            '{"category": "clinical_advice", "answer": "I recommend drinking warm water."}'
        ]
    )
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="My tummy feels a bit warm after eating", llm=llm, config=cfg
    )

    assert res.category == "clinical_advice"
    assert res.blocked is True
    assert res.text == CLINICAL_REFUSAL_TEXT
    assert "warm water" not in res.text


def test_model_returns_off_topic():
    """Off-topic question triggers fixed OFF_TOPIC_TEXT."""
    llm = FakeLLM(
        ['{"category": "off_topic", "answer": "I do not know about football."}']
    )
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="Who won the World Cup in 1998?", llm=llm, config=cfg
    )

    assert res.category == "off_topic"
    assert res.blocked is True
    assert res.text == OFF_TOPIC_TEXT


def test_malformed_json_retry_once_success():
    """Malformed JSON retries once with LLM and succeeds if second attempt is valid."""
    llm = FakeLLM(
        [
            "not json at all",
            '{"category": "faq", "answer": "Visiting hours are 8am to 8pm."}',
        ]
    )
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="What are the visiting hours?", llm=llm, config=cfg
    )

    assert res.category == "faq"
    assert res.blocked is False
    assert res.text == "Visiting hours are 8am to 8pm."
    assert len(llm.calls) == 2


def test_malformed_json_twice_fallback():
    """Two consecutive malformed JSON responses return FALLBACK_TEXT."""
    llm = FakeLLM(["bad json 1", "bad json 2"])
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="What are the visiting hours?", llm=llm, config=cfg
    )

    assert res.category == "unparseable"
    assert res.blocked is True
    assert res.text == FALLBACK_TEXT
    assert len(llm.calls) == 2


def test_output_guard_replaces_dose_answer():
    """If model classifies faq but outputs a dose, output guard replaces it with clinical refusal."""
    llm = FakeLLM(
        ['{"category": "faq", "answer": "You should take 500 mg every morning."}']
    )
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(
        history=[], text="How do I take my medication?", llm=llm, config=cfg
    )

    assert res.category == "clinical_advice"
    assert res.blocked is True
    assert res.text == CLINICAL_REFUSAL_TEXT
    assert "500 mg" not in res.text


def test_blocked_turns_not_sent_back_to_model():
    """Turns with blocked=True are excluded from prompt history sent to LLM."""
    history = [
        {"role": "user", "content": "I have chest pain", "blocked": True},
        {"role": "assistant", "content": EMERGENCY_TEXT, "blocked": True},
        {"role": "user", "content": "Where is the pharmacy?", "blocked": False},
        {"role": "assistant", "content": "Ground floor.", "blocked": False},
    ]
    llm = FakeLLM(['{"category": "faq", "answer": "Yes, 24 hours."}'])
    cfg = Config(gemini_api_key="test-key")
    res = handle_turn(history=history, text="Is it open now?", llm=llm, config=cfg)

    assert res.category == "faq"
    assert len(llm.calls) == 1
    sent_contents = llm.calls[0]["contents"]
    sent_texts = [msg.text for msg in sent_contents]

    # Blocked turn text must not be in context
    assert "I have chest pain" not in sent_texts
    assert EMERGENCY_TEXT not in sent_texts

    # Allowed turn text must be in context
    assert "Where is the pharmacy?" in sent_texts
    assert "Ground floor." in sent_texts
    assert "Is it open now?" in sent_texts


def test_history_window_keeps_last_n_non_blocked_turns():
    """History window sends at most max_history_turns pairs."""
    history = []
    for i in range(15):
        history.append({"role": "user", "content": f"Question {i}", "blocked": False})
        history.append(
            {"role": "assistant", "content": f"Answer {i}", "blocked": False}
        )

    llm = FakeLLM(['{"category": "faq", "answer": "Recent answer."}'])
    cfg = Config(gemini_api_key="test-key", max_history_turns=5)
    res = handle_turn(history=history, text="New question", llm=llm, config=cfg)

    assert res.category == "faq"
    sent_contents = llm.calls[0]["contents"]
    # Last 5 turn pairs = 10 messages, plus 1 new user question = 11 messages
    assert len(sent_contents) == 11
    assert sent_contents[-1].text == "New question"
    assert sent_contents[0].text == "Question 10"
