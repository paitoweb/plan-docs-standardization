import audit_docs_model as adm
import docs_first_config as dfc


def _codes(findings):
    return {f.code for f in findings}


def _write_cfg(repo, **kwargs):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(**kwargs)), encoding="utf-8")


def test_no_config_no_finding(tmp_path):
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert findings == []


def test_valid_config_no_finding(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert findings == []


def test_unknown_profile_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["windsurf"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert _codes(findings) == {"DOCS_FIRST_CONFIG_INVALID"}
    assert findings[0].severity == "WARN"


def test_unknown_gate_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["telepathy"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert _codes(findings) == {"DOCS_FIRST_CONFIG_INVALID"}


def test_audit_does_not_crash_on_malformed_config(tmp_path):
    # Regression: a bad config must degrade gracefully, never crash the audit gate.
    (tmp_path / "docs").mkdir()
    target = tmp_path / dfc.CONFIG_REL
    target.parent.mkdir(parents=True)
    target.write_text("version: oops\nprofiles: [claude]\n", encoding="utf-8")
    result = adm.audit_repository(tmp_path)  # must not raise
    assert "summary" in result


def test_audit_run_never_writes_config(tmp_path):
    # Spec §10: a read-only audit must never write .docs-first/config.yml.
    (tmp_path / "docs").mkdir()
    adm.audit_repository(tmp_path)
    assert not (tmp_path / dfc.CONFIG_REL).exists()
