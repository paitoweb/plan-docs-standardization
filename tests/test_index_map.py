from pathlib import Path

import audit_docs_model as adm

NAV = [
    "docs/PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/GLOSSARY.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/nfr/NON_FUNCTIONAL.md",
    "docs/features/INDEX.md",
    "docs/reports/README.md",
]


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


def test_index_map_no_finding_when_index_absent(tmp_path):
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []
