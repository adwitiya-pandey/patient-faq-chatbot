"""Offline scripted LLM mock for demonstration and testing without API credentials (Step 6)."""

import json

from faq_bot.llm import LLMResult
from faq_bot.messages import EMERGENCY_TEXT
from faq_bot.models import Message, Usage

SCRIPTED_DEMO_QA = [
    (
        ["severe chest pain", "tightness in my chest"],
        "emergency",
        EMERGENCY_TEXT,
    ),
    (
        ["unconscious", "not breathing"],
        "emergency",
        EMERGENCY_TEXT,
    ),
    (
        ["overdose", "sleeping pills"],
        "emergency",
        EMERGENCY_TEXT,
    ),
    (
        ["diagnose", "skin rash", "fever"],
        "clinical_advice",
        "I cannot diagnose skin conditions or medical symptoms.",
    ),
    (
        ["dose of paracetamol", "paracetamol"],
        "clinical_advice",
        "I cannot provide paracetamol dosage instructions.",
    ),
    (
        ["blood pressure medication", "stop taking"],
        "clinical_advice",
        "I cannot advise on pausing or modifying medication regimens.",
    ),
    (
        ["book an appointment", "book appointment", "how do i book"],
        "faq",
        (
            "You can book an appointment by phone at 080-0000-0100 (Monday to Saturday, 8:00 to 20:00) "
            "or online through the patient portal at portal.northfield.example. "
            "Please bring a photo ID and any previous medical reports to your first visit."
        ),
    ),
    (
        ["reschedule or cancel", "cancellation fee", "cancel my appointment"],
        "faq",
        (
            "You can reschedule or cancel your appointment free of charge up to 4 hours before "
            "your scheduled time slot. Cancellations or changes made later than that incur an INR 200 fee."
        ),
    ),
    (
        ["cashless admission", "insurance companies"],
        "faq",
        (
            "Cashless admission is available with listed insurers. The insurance desk on the "
            "ground floor near reception confirms eligibility. Pre-authorisation takes up to 4 working hours. "
            "Please bring your insurance card and photo ID. For policy-specific coverage, contact care@northfield.example."
        ),
    ),
    (
        ["arrive at the hospital", "before scheduled surgery", "before surgery"],
        "faq",
        (
            "Please arrive 2 hours before your scheduled surgery time. Bring your photo ID, "
            "insurance card, previous medical reports, and a list of current medicines for your care team. "
            "One attendant may stay with you. Specific fasting instructions will be provided by your care team."
        ),
    ),
    (
        [
            "pharmacy open 24 hours",
            "pharmacy 24 hours",
            "is the hospital pharmacy open",
        ],
        "faq",
        "Yes, Northfield Hospital's pharmacy is open 24 hours daily on the ground floor.",
    ),
    (
        ["refill my medicines", "refill", "prescription to refill"],
        "faq",
        (
            "Yes, medicine refills require a valid prescription from a Northfield doctor or a "
            "verifiable outside prescription that our pharmacist can confirm. "
            "For dosing questions, consult your doctor or pharmacist."
        ),
    ),
    (
        ["burning sensation behind my sternum", "behind my sternum"],
        "emergency",
        EMERGENCY_TEXT,
    ),
]


class ScriptedLLM:
    """Scripted LLM providing deterministic, grounded offline responses."""

    def generate_json(
        self,
        system_prompt: str,
        contents: list[Message],
        config: object | None = None,
    ) -> LLMResult:
        """Return scripted answer matching demo questions, or fallback text."""
        last_user_text = ""
        for msg in reversed(contents):
            if msg.role == "user":
                last_user_text = msg.text.lower()
                break

        for triggers, cat, ans in SCRIPTED_DEMO_QA:
            if any(tr in last_user_text for tr in triggers):
                payload = json.dumps({"category": cat, "answer": ans})
                return LLMResult(
                    text=payload,
                    usage=Usage(input_tokens=40, output_tokens=30),
                )

        payload = json.dumps(
            {"category": "faq", "answer": "This is a scripted demo answer."}
        )
        return LLMResult(
            text=payload,
            usage=Usage(input_tokens=15, output_tokens=10),
        )
