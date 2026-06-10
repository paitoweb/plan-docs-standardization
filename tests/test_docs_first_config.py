import docs_first_config as dfc


def test_render_emits_flat_yaml_with_inline_lists():
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "cursor"],
        enforcement_chosen=["ci", "local-hook"],
        enforcement_declined=["claude-hooks"],
        updated="2026-06-10",
    )
    text = dfc.render_config(cfg)
    assert "version: 1" in text
    assert "profiles: [claude, cursor]" in text
    assert "enforcement_chosen: [ci, local-hook]" in text
    assert "enforcement_declined: [claude-hooks]" in text
    assert "updated: 2026-06-10" in text


def test_render_emits_empty_lists_as_brackets():
    cfg = dfc.DocsFirstConfig(profiles=[], enforcement_chosen=[], enforcement_declined=[])
    text = dfc.render_config(cfg)
    assert "profiles: []" in text
    assert "enforcement_chosen: []" in text


def test_config_rel_constant():
    assert dfc.CONFIG_REL == ".docs-first/config.yml"
