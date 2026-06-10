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
