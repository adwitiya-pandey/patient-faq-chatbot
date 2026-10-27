"""Fixed UI and safety message constants."""

DISCLAIMER = (
    "I am an automated assistant for Northfield Hospital's patient FAQs. "
    "I am not a medical professional and cannot give medical advice."
)

CLINICAL_REFUSAL_TEXT = (
    "I can't help with diagnosis, symptoms, medicines or doses. "
    "Please talk to your doctor or care team. I can help with appointments, insurance, "
    "preparing for surgery, and pharmacy information."
)

EMERGENCY_TEXT = (
    "If this is an emergency, call 112 now or go to the nearest emergency department. "
    "Northfield's emergency desk is 080-0000-0911 (24 hours). I can't help with emergencies in this chat."
)

OFF_TOPIC_TEXT = (
    "I can only help with Northfield Hospital's appointments, insurance, "
    "surgery preparation and pharmacy questions."
)

EMPTY_TEXT = "Please type a question."

TOO_LONG_TEXT = "That message is too long. Please keep it under 500 characters."

FALLBACK_TEXT = (
    "Sorry, I could not process that. Please rephrase, or call 080-0000-0100."
)

LLM_ERROR_TEXT = "The assistant is unavailable right now. Please call 080-0000-0100 (8:00 to 20:00, Mon to Sat)."

UNGROUNDED_CONTACT_FALLBACK_TEXT = "Please call the front desk at 080-0000-0100."

RATE_LIMIT_TEXT = (
    "You are sending messages too quickly or have reached the session turn limit. "
    "Please wait a moment or start a new session."
)

DAILY_CAP_TEXT = (
    "The service has reached its daily limit. Please try again tomorrow, "
    "or call Northfield Hospital at 080-0000-0100."
)
