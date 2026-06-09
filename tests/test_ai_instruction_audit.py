from pathlib import Path

import audit_docs_model as adm

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "templates" / "ai-instructions" / "guidelines.en.md"


def test_canonical_template_exists_with_two_sections():
    assert TEMPLATE.exists(), "canonical guidelines template must exist"
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Workflow: New Feature" in text
    assert "## Working Principles" in text


def test_section_span_finds_level2_section():
    text = "# Title\n\n## A\nbody a\n\n## B\nbody b\n"
    lines = text.splitlines()
    assert adm.section_span(lines, "## A") == (2, 5)
    assert adm.section_span(lines, "## B") == (5, 7)
    assert adm.section_span(lines, "## Missing") is None


def test_section_span_stops_at_next_level2_not_level3():
    text = "## A\nbody\n### Sub\nmore\n## B\n"
    lines = text.splitlines()
    start, end = adm.section_span(lines, "## A")
    assert lines[start:end] == ["## A", "body", "### Sub", "more"]


def test_extract_section_returns_text_or_none():
    text = "## A\nbody a\n## B\nbody b\n"
    assert adm.extract_section(text, "## A") == "## A\nbody a"
    assert adm.extract_section(text, "## Z") is None


def test_normalize_block_collapses_blanks_and_trims():
    raw = "  ## A  \n\n\nbody\n\n"
    assert adm.normalize_block(raw) == "## A\n\nbody"


def test_load_canonical_sections_returns_two_sections():
    sections = adm.load_canonical_sections()
    assert set(sections) == {"## Workflow: New Feature", "## Working Principles"}
    assert sections["## Workflow: New Feature"].startswith("## Workflow: New Feature")
    assert "traceability" in sections["## Working Principles"]


def _canonical_text():
    sections = adm.load_canonical_sections()
    return "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)


def _codes_for(findings, path):
    return {f.code for f in findings if f.path == path}


def test_absent_files_report_info(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    info_codes = {f.code for f in findings if f.severity == "INFO"}
    assert info_codes == {"AI_INSTRUCTION_FILE_ABSENT"}
    absent_paths = {f.path for f in findings}
    assert absent_paths == set(adm.AI_INSTRUCTION_FILES)


def test_identical_file_produces_no_finding(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n" + _canonical_text() + "\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert _codes_for(findings, "CLAUDE.md") == set()


def test_missing_section_is_blocker(tmp_path):
    sections = adm.load_canonical_sections()
    only_first = sections["## Workflow: New Feature"]
    (tmp_path / "CLAUDE.md").write_text(only_first + "\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md" and f.severity == "BLOCKER"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert "principles" in blockers[0].message.lower()


def test_copilot_nested_path_detected(tmp_path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "copilot-instructions.md").write_text("# x\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = _codes_for(findings, ".github/copilot-instructions.md")
    assert codes == {"AI_INSTRUCTION_SECTION_MISSING"}
