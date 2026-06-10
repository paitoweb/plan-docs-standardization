from pathlib import Path

import audit_docs_model as adm
from audit_docs_model import INDEX_MAP_NAVIGABLE as NAV


def _write_index(repo: Path, body: str) -> None:
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.md").write_text(body, encoding="utf-8")


def _codes(findings):
    return {f.code for f in findings}


def test_index_map_missing_when_no_links(tmp_path):
    _write_index(tmp_path, "# Docs\n\nNothing here.\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert _codes(findings) == {"INDEX_MAP_MISSING"}
    assert findings[0].severity == "WARN"


def test_index_map_present_when_majority_linked(tmp_path):
    links = "\n".join(f"- [doc]({rel[len('docs/'):]})" for rel in NAV)
    _write_index(tmp_path, "# Docs\n\n" + links + "\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_index_map_warns_below_strict_majority(tmp_path):
    # 4 of 9 navigable docs linked -> not a strict majority -> WARN
    links = "\n".join(f"- [doc]({rel[len('docs/'):]})" for rel in NAV[:4])
    _write_index(tmp_path, "# Docs\n\n" + links + "\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert _codes(findings) == {"INDEX_MAP_MISSING"}


def test_index_map_passes_at_minimum_strict_majority(tmp_path):
    # 5 of 9 is the minimum strict majority -> no WARN
    links = "\n".join(f"- [doc]({rel[len('docs/'):]})" for rel in NAV[:5])
    _write_index(tmp_path, "# Docs\n\n" + links + "\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_index_map_no_finding_when_index_absent(tmp_path):
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_ai_file_without_pointer_gets_info(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Project\n\nNo pointer here.\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    info = {f.code for f in findings if f.severity == "INFO" and f.path == "CLAUDE.md"}
    assert "AI_INSTRUCTION_MAP_POINTER_MISSING" in info


def test_ai_file_with_pointer_has_no_pointer_finding(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\nSee [the map](docs/index.md).\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {f.code for f in findings if f.path == "CLAUDE.md"}
    assert "AI_INSTRUCTION_MAP_POINTER_MISSING" not in codes


def test_pointer_missing_is_never_blocker(tmp_path):
    # workflow + principles present (no BLOCKER), but no docs/index.md pointer
    sections = adm.load_canonical_sections()
    text = "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)
    (tmp_path / "CLAUDE.md").write_text(text + "\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = {f.code for f in findings if f.severity == "BLOCKER" and f.path == "CLAUDE.md"}
    assert blockers == set()
    info = {f.code for f in findings if f.severity == "INFO" and f.path == "CLAUDE.md"}
    assert info == {"AI_INSTRUCTION_MAP_POINTER_MISSING"}


def test_audit_repository_runs_index_map_check(tmp_path):
    # Minimal repo with a docs/index.md that has no map -> result includes the WARN code.
    _write_index(tmp_path, "# Docs\n\nno map\n")
    result = adm.audit_repository(tmp_path)
    codes = {f["code"] for f in result["findings"]}
    assert "INDEX_MAP_MISSING" in codes


def test_current_state_absence_is_never_a_finding(tmp_path):
    # A repo without docs/reports/CURRENT_STATE.md must not produce any finding for it.
    _write_index(tmp_path, "# Docs\n\nno map\n")
    result = adm.audit_repository(tmp_path)
    paths = {f["path"] for f in result["findings"]}
    assert "docs/reports/CURRENT_STATE.md" not in paths
    codes = {f["code"] for f in result["findings"]}
    assert not any("CURRENT_STATE" in code for code in codes)
