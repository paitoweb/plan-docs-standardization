from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "templates" / "ai-instructions" / "guidelines.en.md"


def test_canonical_template_exists_with_two_sections():
    assert TEMPLATE.exists(), "canonical guidelines template must exist"
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Workflow: New Feature" in text
    assert "## Working Principles" in text
