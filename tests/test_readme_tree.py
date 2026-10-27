"""Verify that all files in README repository tree exist in the working directory (Step 7)."""

import re
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_readme_tree_files_exist():
    """Verify that every file mentioned in the README.md repository tree exists on disk."""
    root = get_project_root()
    readme_path = root / "README.md"
    assert readme_path.is_file(), "README.md must exist"

    content = readme_path.read_text(encoding="utf-8")

    # Find the repository layout code block
    match = re.search(
        r"## Repository Layout\s+```(?:text)?\n(.*?)\n```", content, re.DOTALL
    )
    assert match, "Repository Layout code block not found in README.md"

    tree_text = match.group(1)

    # Extract file paths from tree lines like:
    # ├── src/faq_bot/chat.py      # Description
    # │   ├── config.py           # Description
    lines = tree_text.splitlines()

    checked_files = 0

    # Map of explicit files to verify based on filenames in the tree
    for line in lines:
        # Strip tree drawing characters and comments
        cleaned = re.sub(r"^[│├──└──\s]+", "", line)
        if not cleaned or cleaned.startswith("#") or cleaned == "patient-faq-chatbot/":
            continue

        file_part = cleaned.split("#")[0].strip().rstrip("/")
        if not file_part:
            continue

        # Look for the file in the repository
        matching = list(root.glob(f"**/{file_part}"))
        if not matching:
            # Check direct relative path from root
            direct_path = root / file_part
            assert direct_path.exists(), (
                f"Path from README tree does not exist: {file_part}"
            )
        checked_files += 1

    assert checked_files >= 25, (
        f"Expected at least 25 files verified from tree, got {checked_files}"
    )
