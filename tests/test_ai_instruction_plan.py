import audit_docs_model as adm
import build_docs_alignment_plan as plan


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


def test_ai_instruction_update_diff_identical_file_reports_no_changes(tmp_path):
    sections = adm.load_canonical_sections()
    text = "# Project\n\nSee [docs/index.md](docs/index.md).\n\n" + "\n\n".join(
        sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS
    ) + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert diff == "No changes required."


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
