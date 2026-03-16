import pathlib
import re


MEMORY_DIR = pathlib.Path.home() / ".open-assistant" / "memory"
EXPECTED_FILES = [
    "index.md",
    "projects.md",
    "commitments.md",
    "preferences.md",
    "procrastination.md",
    "german-life.md",
]


def test_memory_dir_exists():
    assert MEMORY_DIR.is_dir(), f"Memory directory not found: {MEMORY_DIR}"


def test_all_memory_files_exist():
    for name in EXPECTED_FILES:
        assert (MEMORY_DIR / name).exists(), f"Missing memory file: {name}"


def test_index_format():
    """Every non-blank line in index.md must be '- topic: description → filename'."""
    index = (MEMORY_DIR / "index.md").read_text()
    for line in index.strip().splitlines():
        if not line.strip():
            continue
        assert line.startswith("- "), f"Bad index line: {line!r}"
        assert " → " in line, f"Missing ' → ' in index line: {line!r}"


def test_procrastination_entry_format():
    """Entries must start with '- [YYYY-MM-DD added]' so age can be calculated."""
    content = (MEMORY_DIR / "procrastination.md").read_text()
    entries = [l for l in content.splitlines() if l.startswith("- [")]
    for entry in entries:
        assert re.match(r"^- \[\d{4}-\d{2}-\d{2} added\]", entry), (
            f"Bad procrastination entry format: {entry!r}"
        )
