import audit_docs_model as adm
import docs_first_config as dfc


def _codes(findings):
    return {f.code for f in findings}


def test_suggests_when_absent_in_docs_repo(tmp_path):
    (tmp_path / "docs" / "reports").mkdir(parents=True)  # alignment mode, no CURRENT_STATE.md
    findings = []
    adm.check_current_state_suggestion(tmp_path, findings)
    assert _codes(findings) == {"CURRENT_STATE_SUGGESTED"}
    assert findings[0].severity == "INFO"


def test_no_suggestion_when_present(tmp_path):
    reports = tmp_path / "docs" / "reports"
    reports.mkdir(parents=True)
    (reports / "CURRENT_STATE.md").write_text("# Current State\n", encoding="utf-8")
    findings = []
    adm.check_current_state_suggestion(tmp_path, findings)
    assert findings == []


def test_no_suggestion_when_declined(tmp_path):
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    target = tmp_path / dfc.CONFIG_REL
    target.parent.mkdir(parents=True)
    target.write_text(
        dfc.render_config(dfc.DocsFirstConfig(profiles=["claude"], snapshot_declined=True)),
        encoding="utf-8",
    )
    findings = []
    adm.check_current_state_suggestion(tmp_path, findings)
    assert findings == []


def test_no_suggestion_in_bootstrap_mode(tmp_path):
    # no docs/ -> bootstrap; do not nag about an optional snapshot
    findings = []
    adm.check_current_state_suggestion(tmp_path, findings)
    assert findings == []
