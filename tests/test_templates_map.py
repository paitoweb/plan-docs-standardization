from pathlib import Path

import audit_docs_model as adm

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "assets" / "templates"


def test_index_template_has_documentation_map_section():
    text = (TPL / "docs" / "index.md").read_text(encoding="utf-8")
    assert "## Documentation Map" in text
    assert "Boundary rule" in text or "boundary rule" in text.lower()


def test_index_template_passes_index_map_check(tmp_path):
    # Rendered index template must itself qualify as a navigational map.
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    text = (TPL / "docs" / "index.md").read_text(encoding="utf-8").replace(
        "{{PROJECT_NAME}}", "Demo"
    )
    (docs / "index.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_guidelines_template_has_map_section_and_pointer():
    text = (TPL / "ai-instructions" / "guidelines.en.md").read_text(encoding="utf-8")
    assert "## Documentation Map" in text
    assert "(docs/index.md)" in text  # markdown link to the map


def test_load_canonical_map_section_returns_map():
    section = adm.load_canonical_map_section()
    assert section.startswith("## Documentation Map")
    assert "docs/index.md" in section


def test_current_state_template_exists_and_is_snapshot():
    text = (TPL / "docs" / "reports" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    assert "NOT append-only" in text
    assert "Where we are" in text
