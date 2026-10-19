"""Deterministic input validation, PII redaction, and safety pre-checks."""

import re

# Emergency patterns: acute life-threatening emergencies that require immediate medical attention.
EMERGENCY = [
    r"\bchest (pain|tightness)\b",  # Cardiac distress or heart attack symptoms
    r"\bcan[’']?t breathe\b",  # Acute dyspnea or respiratory distress (with straight, curly, or no apostrophe)
    r"\bcannot breathe\b",  # Severe respiratory failure
    r"\bunable to breathe\b",  # Inability to breathe
    r"\b(difficulty|trouble) breathing\b",  # Breathing impairment or obstruction
    r"\bshort(ness)? of breath\b",  # Acute shortness of breath
    r"\bnot breathing\b",  # Apnea or respiratory arrest
    r"\bunconscious\b",  # Loss of consciousness or unresponsive patient
    r"\b(heavy|severe) bleeding\b",  # Uncontrolled hemorrhage
    r"\bbleeding (heavily|a lot)\b",  # Profuse bleeding
    r"\bstroke\b",  # Cerebrovascular accident symptoms
    r"\bseizure\b",  # Convulsive episode or epilepsy
    r"\boverdos\w*\b",  # Toxic medication or drug overdose
    r"\bsuicid\w*\b",  # Suicidal ideation or actions
    r"\bkill myself\b",  # Direct self-harm statement
    r"\bend my life\b",  # Self-harm intent
    r"\bwant to die\b",  # Suicidal ideation
    r"\banaphyla\w*\b",  # Anaphylactic shock or severe allergic reaction
    r"\bpoison\w*\b",  # Ingestion of poisons or toxic chemicals
]

# Clinical advice patterns: medical queries requesting diagnosis, treatment, dosing, or interpretation.
CLINICAL = [
    r"\bdiagnos\w*",  # Direct diagnosis requests
    r"\bsymptom\w*",  # Inquiries interpreting symptoms
    r"\bdo i have (?!to\b|an? (appointment|booking|insurance|policy)\b)",  # Self-diagnosis questions, excluding logistics
    r"\bwhat(?:’s|'s| is) wrong with me\b",  # Inquiries about illness cause
    r"\bam i (sick|ill|dying)\b",  # Health status or mortality anxiety
    r"\bwhat (disease|illness|condition)\b",  # Disease identification requests
    r"\bis (it|this|that)\b.*\b(cancer|tumou?r|serious|dangerous|infectious)\b",  # Malignancy and seriousness assessments
    r"\bshould i (take|stop|skip|increase|decrease|double|continue)\b",  # Medication regimen modification advice
    r"\bhow (much|many)\b.*\b(tablet|pill|capsule|drop|dose|mg|ml)s?\b",  # Dosage quantification inquiries
    r"\b(dosage|dose)\b",  # Inquiries directly asking for drug dosages
    r"\b[0-9]+(\.[0-9]+)?\s?(mg|mcg|ml|iu)\b",  # Specific clinical dose values
    r"\bside[- ]effects?\b",  # Inquiries about drug side effects
    r"\binteraction\w*\b",  # Drug-drug or food-drug interaction inquiries
    r"\bsafe to (take|eat|drink|use)\b",  # Medication safety and consumption checks
    r"\bcan i (take|use|mix)\b.*\b(with|and)\b",  # Drug mixing and co-administration queries
    r"\bwhich (medicine|medication|tablet|drug)s?\b",  # Drug selection recommendations
    r"\bwhat (medicine|medication|tablet|drug)s?\b.*\b(good|best|cure|treat)\b",  # Drug efficacy recommendations
    r"\b(treatment|cure|remedy) for\b",  # Therapy or cure recommendations
    r"\bprescribe\b",  # Requests for prescription or off-label use
    r"\b(what does|what do|interpret|explain|mean)\b.*\b(result|report|scan|test)s?\b",  # Diagnostic report interpretation
]

# Pre-compiled case-insensitive regex lists
EMERG_RE = [re.compile(p, re.IGNORECASE) for p in EMERGENCY]
CLIN_RE = [re.compile(p, re.IGNORECASE) for p in CLINICAL]

# Output guardrail pattern detecting dose-like numbers in model answers
OUTPUT_DOSE_RE = re.compile(
    r"\b[0-9]+(\.[0-9]+)?\s?(mg|mcg|µg|ml|iu|units?)\b", re.IGNORECASE
)

# PII redaction patterns for email, mobile phone, and 12-digit identity numbers
PII = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+"),
    "mobile": re.compile(r"(?<![0-9])(?:\+91[\s-]?)?[6-9][0-9]{9}(?![0-9])"),
    "id12": re.compile(r"(?<![0-9])[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}(?![0-9])"),
}


def validate_input(text: str, max_chars: int = 500) -> tuple[str, str | None]:
    """Validate user input.

    Returns:
        tuple[str, str | None]: (cleaned_text, error_type).
        error_type is 'empty' if string is blank, 'too_long' if exceeding max_chars, or None.
    """
    stripped = text.strip()
    if not stripped:
        return "", "empty"
    if len(stripped) > max_chars:
        return stripped, "too_long"
    return stripped, None


def redact_pii(text: str) -> tuple[str, bool]:
    """Redact email, Indian mobile phone numbers, and 12-digit IDs from user text.

    Returns:
        tuple[str, bool]: (redacted_text, hit_flag).
    """
    hit = False
    for pattern in PII.values():
        text, count = pattern.subn("[REDACTED]", text)
        if count > 0:
            hit = True
    return text, hit


def precheck(text: str) -> str | None:
    """Deterministic regex pre-check before calling the LLM.

    Returns:
        'emergency', 'clinical_advice', or None if input passes through safely.
        Emergency strictly takes precedence over clinical advice.
    """
    if any(pattern.search(text) for pattern in EMERG_RE):
        return "emergency"
    if any(pattern.search(text) for pattern in CLIN_RE):
        return "clinical_advice"
    return None


def output_guard(text: str) -> bool:
    """Examine generated answer text for dose-like numerical values.

    Returns:
        True if dose-like text is detected (blocked), False otherwise.
    """
    return bool(OUTPUT_DOSE_RE.search(text))
