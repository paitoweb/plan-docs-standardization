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


def test_parse_round_trip():
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "cursor"],
        enforcement_chosen=["ci"],
        enforcement_declined=[],
        updated="2026-06-10",
    )
    parsed = dfc.parse_config(dfc.render_config(cfg))
    assert parsed.profiles == ["claude", "cursor"]
    assert parsed.enforcement_chosen == ["ci"]
    assert parsed.enforcement_declined == []
    assert parsed.updated == "2026-06-10"
    assert parsed.version == 1


def test_parse_handles_empty_lists_and_comments():
    text = "# comment\nversion: 1\nprofiles: []\nenforcement_chosen: []\nenforcement_declined: []\n"
    parsed = dfc.parse_config(text)
    assert parsed.profiles == []
    assert parsed.enforcement_chosen == []


def test_load_config_missing_returns_none(tmp_path):
    assert dfc.load_config(tmp_path) is None


def test_load_config_reads_file(tmp_path):
    target = tmp_path / dfc.CONFIG_REL
    target.parent.mkdir(parents=True)
    target.write_text(
        dfc.render_config(dfc.DocsFirstConfig(profiles=["codex"])), encoding="utf-8"
    )
    parsed = dfc.load_config(tmp_path)
    assert parsed is not None
    assert parsed.profiles == ["codex"]
