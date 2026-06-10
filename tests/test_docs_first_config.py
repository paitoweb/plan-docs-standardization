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


def test_save_config_creates_dir_and_file(tmp_path):
    cfg = dfc.DocsFirstConfig(profiles=["cursor"], enforcement_chosen=["ci"], updated="2026-06-10")
    path = dfc.save_config(tmp_path, cfg)
    assert path == tmp_path / dfc.CONFIG_REL
    assert path.exists()
    assert (tmp_path / ".docs-first").is_dir()


def test_save_config_round_trips_through_load(tmp_path):
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "codex"],
        enforcement_chosen=["local-hook"],
        enforcement_declined=["ci"],
        updated="2026-06-10",
    )
    dfc.save_config(tmp_path, cfg)
    loaded = dfc.load_config(tmp_path)
    assert loaded.profiles == ["claude", "codex"]
    assert loaded.enforcement_chosen == ["local-hook"]
    assert loaded.enforcement_declined == ["ci"]


def test_save_config_overwrites_existing(tmp_path):
    dfc.save_config(tmp_path, dfc.DocsFirstConfig(profiles=["claude"]))
    dfc.save_config(tmp_path, dfc.DocsFirstConfig(profiles=["cursor"]))
    loaded = dfc.load_config(tmp_path)
    assert loaded.profiles == ["cursor"]


def test_parse_config_tolerates_bad_version(tmp_path):
    # A malformed config must never crash the parser (it feeds the audit gate).
    cfg = dfc.parse_config("version: notanint\nprofiles: [claude]\n")
    assert cfg.profiles == ["claude"]
    assert cfg.version == dfc.SCHEMA_VERSION


def test_load_config_with_bad_version_does_not_raise(tmp_path):
    target = tmp_path / dfc.CONFIG_REL
    target.parent.mkdir(parents=True)
    target.write_text("version: oops\nprofiles: [cursor]\n", encoding="utf-8")
    cfg = dfc.load_config(tmp_path)
    assert cfg.profiles == ["cursor"]
