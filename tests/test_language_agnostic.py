import audit_docs_model as adm


def test_normalize_section_title_strips_accents_paren_and_case():
    assert adm.normalize_section_title("Visão Geral") == "visao geral"
    assert adm.normalize_section_title("Requisitos (REQ-*)") == "requisitos"
    assert adm.normalize_section_title("  Acceptance   Criteria (AC-*) ") == "acceptance criteria"


def test_feature_section_titles_dedup_and_skip_level3():
    text = "# T\n\n## Visão Geral\nx\n\n## Requisitos (REQ-*)\n### AC-FOO-001\n## Visão Geral\n"
    titles = adm.feature_section_titles(text)
    assert titles == [("visao geral", "Visão Geral"), ("requisitos", "Requisitos (REQ-*)")]


def test_iter_level2_sections_splits_on_level2_only():
    text = "## A\nbody\n### Sub\nmore\n## B\nb2\n"
    sections = adm.iter_level2_sections(text)
    assert sections == [["## A", "body", "### Sub", "more"], ["## B", "b2"]]


def _write_feature(repo, name, sections):
    d = repo / "docs" / "features" / name
    d.mkdir(parents=True)
    body = "\n\n".join(f"## {s}\ncontent" for s in sections) + "\n"
    (d / "README.md").write_text(body, encoding="utf-8")


def test_consistency_passes_when_all_features_match_ptbr(tmp_path):
    secs = ["Visão Geral", "Requisitos (REQ-*)", "Critérios de Aceite (AC-*)"]
    _write_feature(tmp_path, "alpha", secs)
    _write_feature(tmp_path, "beta", secs)
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_consistency_flags_feature_missing_reference_section(tmp_path):
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "FEATURE_SECTION_INCONSISTENT"
    assert f.path == "docs/features/beta/README.md"
    assert "Questões em Aberto" in f.message


def test_consistency_single_feature_no_finding(tmp_path):
    _write_feature(tmp_path, "alpha", ["Overview", "Requirements"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_compute_feature_section_gaps_returns_original_titles(tmp_path):
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/beta/README.md": ["Dependências"]}
