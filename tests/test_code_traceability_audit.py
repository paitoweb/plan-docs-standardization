from pathlib import Path

import audit_code_traceability as act


def _write_traceability(repo: Path, feature_dir: str, source_glob: str, test_glob: str):
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "traceability.json").write_text(
        f'''{{
  "features": [{{
    "feature_dir": "{feature_dir}",
    "source_globs": ["{source_glob}"],
    "test_globs": ["{test_glob}"],
    "exclude_globs": []
  }}]
}}''',
        encoding="utf-8",
    )


def _write_feature_readme(repo: Path, feature_dir: str):
    feature_path = repo / "docs" / "features" / feature_dir
    feature_path.mkdir(parents=True, exist_ok=True)
    (feature_path / "README.md").write_text(
        "- `REQ-DEMO-001` Example requirement.\n",
        encoding="utf-8",
    )


def test_missing_traceability_json_blocker_for_cursor(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: x\ndocs_dir: docs\n", encoding="utf-8")
    findings = act.audit_code_traceability(tmp_path)
    codes = {f.code for f in findings}
    assert "TRACEABILITY_CONFIG_MISSING" in codes


def test_source_missing_req_citation(tmp_path):
    _write_feature_readme(tmp_path, "demo")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("export const x = 1;\n", encoding="utf-8")
    _write_traceability(tmp_path, "demo", "src/**/*.ts", "tests/**/*.ts")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "app.test.ts").write_text(
        "// Traceability: AC-DEMO-001\n", encoding="utf-8"
    )
    findings = act.audit_code_traceability(tmp_path)
    blockers = [f for f in findings if f.code == "SOURCE_MISSING_REQ_CITATION"]
    assert len(blockers) == 1
    assert blockers[0].path == "src/app.ts"


def test_compliant_source_and_test(tmp_path):
    _write_feature_readme(tmp_path, "demo")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text(
        "/** REQ-DEMO-001 */\nexport const x = 1;\n", encoding="utf-8"
    )
    _write_traceability(tmp_path, "demo", "src/**/*.ts", "tests/**/*.ts")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "app.test.ts").write_text(
        "// Traceability: AC-DEMO-001 (REQ-DEMO-001)\n", encoding="utf-8"
    )
    findings = act.audit_code_traceability(tmp_path)
    assert [f for f in findings if f.severity == "BLOCKER"] == []
