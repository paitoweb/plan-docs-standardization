import audit_docs_model as adm


def _codes_for(findings, path):
    return {f.code for f in findings if f.path == path}


def test_cursor_rule_not_checked_when_cursor_inactive(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    paths = {f.path for f in findings}
    assert ".cursor/rules/docs-first.mdc" not in paths


def test_cursor_rule_absent_reports_info_when_cursor_active(tmp_path):
    (tmp_path / ".cursor").mkdir()  # signal -> cursor profile active
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert _codes_for(findings, ".cursor/rules/docs-first.mdc") == {"AI_INSTRUCTION_FILE_ABSENT"}


def test_cursor_rule_present_but_empty_blocks_when_active(tmp_path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "docs-first.mdc").write_text(
        "---\nalwaysApply: true\n---\n\n# nothing structural here\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert "AI_INSTRUCTION_SECTION_MISSING" in _codes_for(
        findings, ".cursor/rules/docs-first.mdc"
    )


def test_targets_helper_dedupes_agents_md(tmp_path):
    (tmp_path / ".codex").mkdir()  # codex soft_target is AGENTS.md, already in base list
    targets = adm.ai_instruction_targets(tmp_path)
    assert targets.count("AGENTS.md") == 1
