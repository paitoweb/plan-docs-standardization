import audit_docs_model as adm
import build_docs_alignment_plan as plan


def _canonical_text():
    sections = adm.load_canonical_sections()
    return "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)


def test_absent_finding_excluded_from_actions():
    result = {
        "findings": [
            {"code": "AI_INSTRUCTION_FILE_ABSENT", "path": "CLAUDE.md", "severity": "INFO"},
            {"code": "MISSING_REQUIRED_FILE", "path": "docs/index.md", "severity": "BLOCKER"},
        ]
    }
    create, alter = plan.collect_actions(result)
    assert "CLAUDE.md" not in create
    assert "CLAUDE.md" not in alter
    assert "docs/index.md" in create


def test_blocker_ai_finding_goes_to_alter():
    result = {
        "findings": [
            {"code": "AI_INSTRUCTION_SECTION_MISSING", "path": "AGENTS.md", "severity": "BLOCKER"},
        ]
    }
    create, alter = plan.collect_actions(result)
    assert alter == ["AGENTS.md"]
    assert create == []


def test_ai_instruction_update_diff_appends_missing_section(tmp_path):
    sections = adm.load_canonical_sections()
    (tmp_path / "CLAUDE.md").write_text(
        sections["## Workflow: New Feature"] + "\n", encoding="utf-8"
    )
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "+## Working Principles" in diff
    assert "## Workflow: New Feature" not in diff.replace("+## Working Principles", "")


def test_ai_instruction_update_diff_replaces_divergent_section(tmp_path):
    sections = adm.load_canonical_sections()
    tampered = sections["## Working Principles"].replace("Pragmatism", "Pragmatism CHANGED")
    text = sections["## Workflow: New Feature"] + "\n\n" + tampered + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "-- **Pragmatism CHANGED**" in diff or "-- **Pragmatism CHANGED**: " in diff
    assert "+- **Pragmatism**" in diff


def test_build_markdown_lists_absent_ai_files(tmp_path):
    result = {
        "mode": "alignment",
        "summary": {"blocker": 0, "warn": 0, "info": 1},
        "findings": [
            {"code": "AI_INSTRUCTION_FILE_ABSENT", "path": "GEMINI.md",
             "severity": "INFO", "message": "absent"},
        ],
    }
    md = plan.build_markdown(tmp_path, result, [], [], [], [])
    assert "AI Instruction Files Absent" in md
    assert "`GEMINI.md`" in md
