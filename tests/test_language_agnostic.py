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
