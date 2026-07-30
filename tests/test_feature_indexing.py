"""A feature the reader cannot find is undocumented in practice.

R008 validated nav -> file and R013 validated index -> canonical docs. Nothing validated
feature -> index, so a feature folder unreachable from both passed the audit.
"""

import audit_docs_model as adm


def _feature(tmp_path, slug):
    feature_dir = tmp_path / "docs" / "features" / slug
    feature_dir.mkdir(parents=True)
    for name in ("README.md", "flows.md", "rules.md", "notes.md"):
        (feature_dir / name).write_text(f"# {slug} {name}\n", encoding="utf-8")
    return feature_dir


def _index(tmp_path, body):
    path = tmp_path / "docs" / "features" / "INDEX.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _mkdocs(tmp_path, nav_yaml):
    (tmp_path / "mkdocs.yml").write_text(f"site_name: x\nnav:\n{nav_yaml}", encoding="utf-8")


def _codes(findings):
    return [f.code for f in findings]


def test_unlinked_feature_blocks(tmp_path):
    _feature(tmp_path, "voice")
    _index(tmp_path, "# Feature Index\n\nNothing here yet.\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert _codes(findings) == ["FEATURE_NOT_IN_INDEX"]
    assert findings[0].severity == "BLOCKER"
    assert findings[0].path == "docs/features/voice"


def test_readme_link_satisfies_the_index(tmp_path):
    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\n| [voice](voice/README.md) |\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []


def test_folder_link_satisfies_the_index(tmp_path):
    """A folder link resolves to its README.md, so both link styles must count."""

    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\n- [`voice/`](voice/)\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []


def test_deep_link_into_the_feature_satisfies_the_index(tmp_path):
    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\n- [flows](voice/flows.md)\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []


def test_missing_nav_entry_blocks_when_nav_enumerates_features(tmp_path):
    _feature(tmp_path, "voice")
    _feature(tmp_path, "tray")
    _index(tmp_path, "# Index\n\n- [voice](voice/README.md)\n- [tray](tray/README.md)\n")
    _mkdocs(tmp_path, "  - Voice: features/voice/README.md\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert _codes(findings) == ["FEATURE_NOT_IN_NAV"]
    assert findings[0].path == "docs/features/tray"


def test_nav_not_enumerating_features_is_never_flagged(tmp_path):
    """mkdocs-awesome-pages / literate-nav setups do not list files; flagging them all
    would be a false positive on a legitimate configuration."""

    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\n- [voice](voice/README.md)\n")
    _mkdocs(tmp_path, "  - Home: index.md\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []


def test_absent_mkdocs_yields_only_the_index_finding(tmp_path):
    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\nempty\n")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert _codes(findings) == ["FEATURE_NOT_IN_INDEX"]


def test_no_features_means_no_findings(tmp_path):
    (tmp_path / "docs" / "features").mkdir(parents=True)
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []


def test_unparseable_mkdocs_does_not_double_report(tmp_path):
    """check_mkdocs_nav already reports the parse error; nav coverage stays silent."""

    _feature(tmp_path, "voice")
    _index(tmp_path, "# Index\n\n- [voice](voice/README.md)\n")
    (tmp_path / "mkdocs.yml").write_text("nav: [unclosed\n", encoding="utf-8")
    findings = []
    adm.check_feature_indexing(tmp_path, findings)
    assert findings == []
    assert adm.mkdocs_nav_refs(tmp_path) == set()


def test_mkdocs_env_tag_is_tolerated_by_the_shared_loader(tmp_path):
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: !ENV [NAME, x]\nnav:\n  - Voice: features/voice/README.md\n",
        encoding="utf-8",
    )
    assert adm.mkdocs_nav_refs(tmp_path) == {"features/voice/README.md"}
