"""System prompt loader and template rendering."""

from pathlib import Path


def get_project_root() -> Path:
    """Return project root directory."""
    return Path(__file__).resolve().parent.parent.parent


def load_faq_text(faq_path: Path | str | None = None) -> str:
    """Read the hospital FAQ markdown file."""
    if faq_path is None:
        faq_path = get_project_root() / "data" / "hospital_faq.md"
    return Path(faq_path).read_text(encoding="utf-8")


def load_system_prompt_template(prompt_path: Path | str | None = None) -> str:
    """Read the system prompt markdown template."""
    if prompt_path is None:
        prompt_path = get_project_root() / "prompts" / "system_prompt.md"
    return Path(prompt_path).read_text(encoding="utf-8")


def build_system_prompt(
    hospital_name: str,
    faq_path: Path | str | None = None,
    prompt_path: Path | str | None = None,
) -> str:
    """Load template and FAQ text, and substitute placeholders."""
    template = load_system_prompt_template(prompt_path)
    faq_text = load_faq_text(faq_path)
    return template.replace("{hospital_name}", hospital_name).replace(
        "{faq_text}", faq_text
    )
