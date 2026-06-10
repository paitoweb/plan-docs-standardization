import audit_docs_model as adm
import docs_first_config as dfc


def _codes(findings):
    return {f.code for f in findings}


def _write_cfg(repo, **kwargs):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(**kwargs)), encoding="utf-8")


def test_chosen_gate_missing_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert "ENFORCEMENT_GATE_MISSING" in _codes(findings)
    assert all(f.severity != "BLOCKER" for f in findings)


def test_chosen_gate_present_no_warn(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    wf = tmp_path / ".github" / "workflows" / "docs-audit.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: x\n", encoding="utf-8")
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert "ENFORCEMENT_GATE_MISSING" not in _codes(findings)


def test_no_gate_in_docs_repo_infos(tmp_path):
    (tmp_path / "docs").mkdir()  # alignment mode
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert _codes(findings) == {"NO_ENFORCEMENT_GATE"}
    assert findings[0].severity == "INFO"


def test_no_gate_in_non_docs_repo_is_quiet(tmp_path):
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert findings == []
