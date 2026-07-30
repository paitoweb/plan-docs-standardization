"""Code-to-docs coverage: features that exist in code but not in docs/features/.

Two instruments with very different precision. The declared feature_map is exact and blocks;
the coverage ratio is a smell signal and warns once, in aggregate.
"""

import audit_docs_model as adm
import docs_first_config as dfc


def _docs(tmp_path, *slugs):
    (tmp_path / "docs").mkdir(exist_ok=True)
    features = tmp_path / "docs" / "features"
    features.mkdir(exist_ok=True)
    for slug in slugs:
        (features / slug).mkdir()
        (features / slug / "README.md").write_text(f"# {slug}\n", encoding="utf-8")


def _code(tmp_path, *rel_dirs):
    for rel in rel_dirs:
        path = tmp_path / rel
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.ts").write_text("export const x = 1\n", encoding="utf-8")


def _config(tmp_path, body):
    (tmp_path / ".docs-first").mkdir(exist_ok=True)
    (tmp_path / ".docs-first" / "config.yml").write_text(body, encoding="utf-8")


def _run(tmp_path):
    findings = []
    adm.check_code_to_docs_coverage(tmp_path, findings)
    return findings


def test_mapped_code_without_feature_doc_blocks(tmp_path):
    _docs(tmp_path)
    _code(tmp_path, "src/voice")
    _config(tmp_path, "feature_map: [src/voice=voice-transcription]\n")

    findings = [f for f in _run(tmp_path) if f.code == "FEATURE_DOC_MISSING"]
    assert len(findings) == 1
    assert findings[0].severity == "BLOCKER"
    assert findings[0].path == "src/voice"
    assert "voice-transcription" in findings[0].message


def test_mapped_code_with_feature_doc_passes(tmp_path):
    _docs(tmp_path, "voice-transcription")
    _code(tmp_path, "src/voice")
    _config(tmp_path, "feature_map: [src/voice=voice-transcription]\n")
    assert [f.code for f in _run(tmp_path)] == []


def test_mapped_path_absent_from_disk_is_not_a_finding(tmp_path):
    """Nothing shipped, so nothing is owed."""

    _docs(tmp_path)
    _config(tmp_path, "feature_map: [src/voice=voice-transcription]\n")
    assert _run(tmp_path) == []


def test_slug_matching_ignores_naming_convention(tmp_path):
    """voiceTranscription, voice-transcription and voice_transcription are one feature."""

    _docs(tmp_path, "voice-transcription")
    _code(tmp_path, "src/voiceTranscription")
    assert _run(tmp_path) == []


def test_low_coverage_is_one_aggregate_warn(tmp_path):
    _docs(tmp_path, "voice")
    _code(tmp_path, "src/voice", "src/tray", "src/viewers", "src/export")

    findings = _run(tmp_path)
    assert len(findings) == 1
    assert findings[0].code == "FEATURE_DOC_COVERAGE_LOW"
    assert findings[0].severity == "WARN"
    assert "1 of 4" in findings[0].message
    assert "25%" in findings[0].message
    assert "smell signal" in findings[0].message


def test_sufficient_coverage_produces_nothing(tmp_path):
    _docs(tmp_path, "voice", "tray")
    _code(tmp_path, "src/voice", "src/tray")
    assert _run(tmp_path) == []


def test_coverage_gate_promotes_the_warn_to_blocker(tmp_path):
    _docs(tmp_path, "voice")
    _code(tmp_path, "src/voice", "src/tray", "src/viewers", "src/export")
    _config(tmp_path, "coverage_gate: true\n")

    findings = _run(tmp_path)
    assert [f.severity for f in findings] == ["BLOCKER"]
    assert findings[0].code == "FEATURE_DOC_COVERAGE_LOW"


def test_configured_minimum_overrides_the_default(tmp_path):
    _docs(tmp_path, "voice")
    _code(tmp_path, "src/voice", "src/tray", "src/viewers", "src/export")

    _config(tmp_path, "coverage_min: 20\n")
    assert _run(tmp_path) == []  # 25% now clears the bar

    _config(tmp_path, "coverage_min: 90\n")
    assert [f.code for f in _run(tmp_path)] == ["FEATURE_DOC_COVERAGE_LOW"]


def test_mapped_units_are_excluded_from_the_heuristic(tmp_path):
    """The ratio surveys unmapped territory; it does not second-guess the exact instrument."""

    _docs(tmp_path, "voice-transcription")
    _code(tmp_path, "src/voice", "src/tray")
    _config(tmp_path, "feature_map: [src/voice=voice-transcription]\n")

    findings = _run(tmp_path)
    # Only src/tray remains a candidate, and it is undocumented -> 0%.
    assert [f.code for f in findings] == ["FEATURE_DOC_COVERAGE_LOW"]
    assert "0 of 1" in findings[0].message
    assert "src/tray" in findings[0].message
    assert "src/voice" not in findings[0].message


def test_build_and_test_directories_are_never_candidates(tmp_path):
    _docs(tmp_path, "voice")
    _code(tmp_path, "src/voice", "src/tests", "src/dist", "src/node_modules", "src/types")
    assert _run(tmp_path) == []  # only src/voice counts, and it is documented


def test_bootstrap_mode_is_silent(tmp_path):
    """No docs yet, so "coverage is low" says nothing useful."""

    _code(tmp_path, "src/voice", "src/tray")
    assert _run(tmp_path) == []


def test_repo_without_a_recognizable_code_root_is_silent(tmp_path):
    _docs(tmp_path)
    _code(tmp_path, "scripts/thing", "references/other")
    assert _run(tmp_path) == []


def test_declared_code_roots_replace_the_conventional_list(tmp_path):
    _docs(tmp_path)
    _code(tmp_path, "modules/voice")
    assert _run(tmp_path) == []  # modules/ is not conventional

    _config(tmp_path, "code_roots: [modules]\n")
    assert [f.code for f in _run(tmp_path)] == ["FEATURE_DOC_COVERAGE_LOW"]


def test_malformed_feature_map_is_reported_as_invalid_config(tmp_path):
    _config(tmp_path, "feature_map: [src/voice, other=]\n")
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert [f.code for f in findings] == ["DOCS_FIRST_CONFIG_INVALID"]
    assert "malformed feature_map" in findings[0].message


def test_out_of_range_coverage_min_is_reported_as_invalid_config(tmp_path):
    _config(tmp_path, "coverage_min: 140\n")
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert [f.code for f in findings] == ["DOCS_FIRST_CONFIG_INVALID"]
    assert "outside 0-100" in findings[0].message


def test_config_roundtrip_preserves_the_new_keys():
    cfg = dfc.DocsFirstConfig(
        feature_map=["src/voice=voice-transcription"],
        code_roots=["modules"],
        coverage_gate=True,
        coverage_min=70,
    )
    parsed = dfc.parse_config(dfc.render_config(cfg))
    assert parsed.feature_map == ["src/voice=voice-transcription"]
    assert parsed.code_roots == ["modules"]
    assert parsed.coverage_gate is True
    assert parsed.coverage_min == 70


def test_feature_map_entries_with_spaces_are_tolerated():
    pairs, malformed = dfc.parse_feature_map(["src/voice = voice-transcription"])
    assert pairs == [("src/voice", "voice-transcription")]
    assert malformed == []
