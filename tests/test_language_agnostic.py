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


def test_compute_feature_section_gaps_tie_breaks_to_alphabetical_first(tmp_path):
    # Equal distinct-section counts; alpha must win the reference tie.
    _write_feature(tmp_path, "alpha", ["Comum", "Só Alpha"])
    _write_feature(tmp_path, "beta", ["Comum", "Só Beta"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/beta/README.md": ["Só Alpha"]}


WORKFLOW_PT = "## Workflow: nova feature\n1. Brainstorm\n2. Spec\n3. Plano\n"
PRINCIPLES_PT = "## Princípios de trabalho\n- Esclarecer\n- Pragmatismo\n- Rastreabilidade\n"


def test_detect_shapes_true_for_ptbr_file():
    text = WORKFLOW_PT + "\n" + PRINCIPLES_PT
    assert adm.detect_ai_instruction_shapes(text) == (True, True)


def test_detect_shapes_requires_distinct_sections():
    # one section has both an ordered list and bullets; the other is plain prose
    text = "## Tudo junto\n1. a\n2. b\n3. c\n- x\n- y\n- z\n## Outra\nprosa\n"
    assert adm.detect_ai_instruction_shapes(text) == (True, False)


def test_check_ai_ptbr_file_passes(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT + "\n" + PRINCIPLES_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert [f for f in findings if f.path == "CLAUDE.md"] == []


def test_check_ai_missing_principles_is_blocker(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert blockers[0].severity == "BLOCKER"


def test_check_ai_absent_is_info(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {(f.path, f.code, f.severity) for f in findings}
    assert ("CLAUDE.md", "AI_INSTRUCTION_FILE_ABSENT", "INFO") in codes


def test_check_ai_both_shapes_missing_yields_two_blockers(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# x\nplain prose only\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md"]
    assert len(blockers) == 2
    assert all(f.code == "AI_INSTRUCTION_SECTION_MISSING" for f in blockers)
    assert any("workflow" in f.message.lower() for f in blockers)
    assert any("principles" in f.message.lower() for f in blockers)
