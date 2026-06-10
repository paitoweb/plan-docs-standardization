import agent_profiles as ap


def test_registry_has_four_known_profiles():
    assert set(ap.PROFILES) == {"claude", "cursor", "codex", "generic"}


def test_claude_profile_fields():
    p = ap.get_profile("claude")
    assert p.soft_target == "CLAUDE.md"
    assert p.soft_wrapper is None
    assert p.skill_install == ".claude/skills/plan-docs-standardization/"
    assert p.native_hard_gate == "claude-hooks"


def test_cursor_profile_uses_mdc_wrapper_and_has_no_native_gate():
    p = ap.get_profile("cursor")
    assert p.soft_target == ".cursor/rules/docs-first.mdc"
    assert p.soft_wrapper == "mdc"
    assert p.skill_install == ".cursor/skills/plan-docs-standardization/"
    assert p.native_hard_gate is None


def test_codex_profile_uses_agents_md_and_agents_skills_path():
    p = ap.get_profile("codex")
    assert p.soft_target == "AGENTS.md"
    assert p.skill_install == ".agents/skills/plan-docs-standardization/"
    assert p.native_hard_gate == "codex-hooks"


def test_generic_profile_has_no_skill_or_gate():
    p = ap.get_profile("generic")
    assert p.soft_target == "AGENTS.md"
    assert p.skill_install is None
    assert p.native_hard_gate is None


def test_get_profile_unknown_raises():
    import pytest

    with pytest.raises(KeyError):
        ap.get_profile("windsurf")


def test_detect_empty_repo_returns_no_profiles(tmp_path):
    assert ap.detect_signal_profiles(tmp_path) == []


def test_detect_cursor_and_claude_dirs(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    assert ap.detect_signal_profiles(tmp_path) == ["claude", "cursor"]


def test_detect_codex_via_either_marker(tmp_path):
    (tmp_path / ".agents").mkdir()
    assert ap.detect_signal_profiles(tmp_path) == ["codex"]


def test_detect_ignores_generic_which_has_no_signal(tmp_path):
    # generic has empty detect_dirs and must never be auto-detected
    (tmp_path / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    assert ap.detect_signal_profiles(tmp_path) == []


import docs_first_config as dfc


def _write_cfg(repo, profiles):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(profiles=profiles)), encoding="utf-8")


def test_resolve_prefers_config(tmp_path):
    _write_cfg(tmp_path, ["codex"])
    (tmp_path / ".cursor").mkdir()  # signal disagrees; config wins
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == ["codex"]
    assert source == "config"


def test_resolve_falls_back_to_signals(tmp_path):
    (tmp_path / ".cursor").mkdir()
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == ["cursor"]
    assert source == "signals"


def test_resolve_undetermined_when_nothing(tmp_path):
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == []
    assert source == "undetermined"
