from pathlib import Path

import audit_docs_model as adm


def _canonical_text():
    sections = adm.load_canonical_sections()
    return "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)


def test_cursor_rule_absent_when_no_cursor_dir(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    cursor_paths = {f.path for f in findings if f.path.startswith(".cursor/")}
    assert cursor_paths == set()


def test_cursor_rule_checked_when_cursor_dir_exists(tmp_path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    cursor_findings = [f for f in findings if f.path == ".cursor/rules/docs-first-workflow.mdc"]
    assert len(cursor_findings) == 1
    assert cursor_findings[0].code == "AI_INSTRUCTION_FILE_ABSENT"
    assert cursor_findings[0].severity == "INFO"


def test_cursor_rule_compliant(tmp_path):
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-first-workflow.mdc").write_text(
        "---\nalwaysApply: true\n---\n\n" + _canonical_text() + "\n",
        encoding="utf-8",
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    cursor_findings = [f for f in findings if f.path == ".cursor/rules/docs-first-workflow.mdc"]
    assert cursor_findings == []
