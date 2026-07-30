import audit_docs_model as adm
import build_docs_alignment_plan as plan


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


def test_consistency_flags_feature_missing_majority_section(tmp_path):
    # 2 of 3 features use "Questões em Aberto" → majority → the third is flagged (WARN)
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "FEATURE_SECTION_INCONSISTENT"
    assert f.severity == "WARN"
    assert f.path == "docs/features/gamma/README.md"
    assert "Questões em Aberto" in f.message


def test_consistency_unique_section_does_not_cascade(tmp_path):
    # one richer feature has an extra section; it must NOT be required of the others
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Métricas"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_consistency_exact_half_is_not_majority(tmp_path):
    # "Extra" is in exactly 2 of 4 features (50%, not a strict majority) → not expected
    _write_feature(tmp_path, "a", ["Visão Geral", "Requisitos", "Extra"])
    _write_feature(tmp_path, "b", ["Visão Geral", "Requisitos", "Extra"])
    _write_feature(tmp_path, "c", ["Visão Geral", "Requisitos"])
    _write_feature(tmp_path, "d", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_consistency_single_feature_no_finding(tmp_path):
    _write_feature(tmp_path, "alpha", ["Overview", "Requirements"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_compute_feature_section_gaps_returns_original_titles(tmp_path):
    # "Dependências" is in 2 of 3 features → majority → the third's gap reports it
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/gamma/README.md": ["Dependências"]}


# A *compliant* pt-BR workflow: localized prose, but routing through the literal path
# `docs/features/`. This is what makes the content check language-agnostic.
WORKFLOW_PT = (
    "## Workflow: nova feature\n"
    "1. Brainstorm\n"
    "2. Doc da feature em `docs/features/<feature>/`\n"
    "3. Plano\n"
)
PRINCIPLES_PT = "## Princípios de trabalho\n- Esclarecer\n- Pragmatismo\n- Rastreabilidade\n"


def test_detect_shapes_true_for_ptbr_file():
    text = WORKFLOW_PT + "\n" + PRINCIPLES_PT
    assert adm.detect_ai_instruction_shapes(text) == (True, True)


def test_detect_shapes_requires_distinct_sections():
    # one section has both an ordered list and bullets; the other is plain prose
    text = "## Tudo junto\n1. a\n2. b\n3. c\n- x\n- y\n- z\n## Outra\nprosa\n"
    assert adm.detect_ai_instruction_shapes(text) == (True, False)


def test_check_ai_ptbr_file_passes(tmp_path):
    pointer = "See [docs/index.md](docs/index.md).\n\n"
    (tmp_path / "CLAUDE.md").write_text(pointer + WORKFLOW_PT + "\n" + PRINCIPLES_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert [f for f in findings if f.path == "CLAUDE.md"] == []


def test_check_ai_missing_principles_is_blocker(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md" and f.severity == "BLOCKER"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert blockers[0].severity == "BLOCKER"


def test_ptbr_workflow_without_feature_docs_path_blocks(tmp_path):
    """The content check must not be a disguised English requirement.

    Same localized file as the passing case, minus the `docs/features/` reference: it blocks
    on the missing reference, not on being written in Portuguese.
    """

    workflow = "## Workflow: nova feature\n1. Brainstorm\n2. Spec\n3. Plano\n"
    (tmp_path / "CLAUDE.md").write_text(workflow + "\n" + PRINCIPLES_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {f.code for f in findings if f.severity == "BLOCKER"}
    assert codes == {"AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED"}


def test_release_ritual_no_longer_satisfies_the_workflow_requirement(tmp_path):
    """The reported real-world false pass: a release ritual plus architecture bullets.

    Both shapes are present, so the structural check is happy, yet nothing says to document
    a feature. This is exactly the file that audited green with 0 BLOCKER, 0 WARN.
    """

    text = (
        "See [docs/index.md](docs/index.md).\n\n"
        "## Release ritual\n1. Bump version\n2. Tag\n3. Publish\n\n"
        "## Architecture\n- Electron main\n- React renderer\n- IPC bridge\n"
    )
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert adm.detect_ai_instruction_shapes(text) == (True, True)  # shape check passes
    assert [f.code for f in findings if f.severity == "BLOCKER"] == [
        "AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED"
    ]


def test_missing_workflow_section_is_not_double_reported(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(PRINCIPLES_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = [f.code for f in findings if f.severity == "BLOCKER"]
    assert codes == ["AI_INSTRUCTION_SECTION_MISSING"]


def test_canonical_block_satisfies_the_content_check():
    text = (adm.skill_root() / adm.CANONICAL_GUIDELINES_REL).read_text(encoding="utf-8")
    assert adm.workflow_routes_through_feature_docs(text)


def test_workflow_reference_is_read_from_the_workflow_section_only(tmp_path):
    """A mention elsewhere must not satisfy it — the *process* has to route through the doc."""

    text = (
        "## Release ritual\n1. Bump\n2. Tag\n3. Publish\n\n"
        "## Notes\n- Specs live in docs/features/ somewhere\n- b\n- c\n"
    )
    assert adm.detect_ai_instruction_shapes(text) == (True, True)
    assert not adm.workflow_routes_through_feature_docs(text)


def test_check_ai_absent_is_info(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {(f.path, f.code, f.severity) for f in findings}
    assert ("CLAUDE.md", "AI_INSTRUCTION_FILE_ABSENT", "INFO") in codes


def test_check_ai_both_shapes_missing_yields_two_blockers(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# x\nplain prose only\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md" and f.severity == "BLOCKER"]
    assert len(blockers) == 2
    assert all(f.code == "AI_INSTRUCTION_SECTION_MISSING" for f in blockers)
    assert any("workflow" in f.message.lower() for f in blockers)
    assert any("principles" in f.message.lower() for f in blockers)


def test_feature_section_append_diff_proposes_missing_headings(tmp_path):
    d = tmp_path / "docs" / "features" / "beta"
    d.mkdir(parents=True)
    (d / "README.md").write_text("## Visão Geral\nx\n", encoding="utf-8")
    diff = plan.feature_section_append_diff(
        tmp_path, "docs/features/beta/README.md", ["Dependências", "Questões em Aberto"]
    )
    assert "+## Dependências" in diff
    assert "+## Questões em Aberto" in diff


def test_ai_update_diff_appends_missing_principles(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "+## Working Principles" in diff
    assert "Working Principles" not in WORKFLOW_PT  # guard: came from canonical, not the file


def test_ai_update_diff_identical_reports_no_changes(tmp_path):
    sections = adm.load_canonical_sections()
    text = (
        "See [docs/index.md](docs/index.md).\n\n"
        + sections["## Workflow: New Feature"]
        + "\n\n"
        + sections["## Working Principles"]
        + "\n"
    )
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    assert plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md") == "No changes required."
