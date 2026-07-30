"""docs/features/ is the single source of truth; design-doc subtrees are outside the model.

A dated design doc under docs/superpowers/specs/ is abandoned by definition, so it must not
be audited at all — its stale links cannot be allowed to fail the gate.
"""

import audit_docs_model as adm


def _write(path, text="[gone](./missing-target.md)\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_broken_link_in_specs_subtree_is_not_reported(tmp_path):
    _write(tmp_path / "docs" / "superpowers" / "specs" / "2026-07-30-x-design.md")
    findings = []
    adm.check_markdown_links(tmp_path, findings)
    assert findings == []


def test_broken_link_elsewhere_in_docs_still_blocks(tmp_path):
    _write(tmp_path / "docs" / "superpowers" / "plans" / "2026-07-30-x.md")
    findings = []
    adm.check_markdown_links(tmp_path, findings)
    assert [f.code for f in findings] == ["BROKEN_INTERNAL_LINK"]


def test_feature_docs_are_never_excluded(tmp_path):
    _write(tmp_path / "docs" / "features" / "specs" / "README.md")
    findings = []
    adm.check_markdown_links(tmp_path, findings)
    assert [f.code for f in findings] == ["BROKEN_INTERNAL_LINK"]


def test_subtree_predicate_matches_only_whole_path_segments(tmp_path):
    assert adm.is_ignored_docs_subtree(
        tmp_path / "docs" / "superpowers" / "specs" / "a.md", tmp_path
    )
    assert not adm.is_ignored_docs_subtree(
        tmp_path / "docs" / "superpowers" / "specs-archive" / "a.md", tmp_path
    )
    assert not adm.is_ignored_docs_subtree(tmp_path / "docs" / "specs" / "a.md", tmp_path)


def test_spec_present_is_reported_once_per_subtree(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    for name in ("a-design.md", "b-design.md", "c-design.md"):
        (specs / name).write_text("# design\n", encoding="utf-8")

    findings = []
    adm.check_specs_outside_feature_docs(tmp_path, findings)

    assert len(findings) == 1
    assert findings[0].code == "SPEC_OUTSIDE_FEATURE_DOCS"
    assert findings[0].severity == "WARN"
    assert findings[0].path == "docs/superpowers/specs"
    assert "3 design document(s)" in findings[0].message
    assert "a-design.md" in findings[0].message


def test_spec_finding_truncates_the_file_list(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    for index in range(9):
        (specs / f"{index}-design.md").write_text("# design\n", encoding="utf-8")

    findings = []
    adm.check_specs_outside_feature_docs(tmp_path, findings)

    assert "9 design document(s)" in findings[0].message
    assert "+4 more" in findings[0].message


def test_empty_or_absent_specs_folder_is_never_a_finding(tmp_path):
    findings = []
    adm.check_specs_outside_feature_docs(tmp_path, findings)
    assert findings == []

    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    adm.check_specs_outside_feature_docs(tmp_path, findings)
    assert findings == []


def test_spec_finding_never_escalates_to_blocker(tmp_path):
    """The rule must not fail a gate: it flags legacy debt, and legacy cannot be rewritten."""

    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "a-design.md").write_text("# design\n", encoding="utf-8")

    result = adm.audit_repository(tmp_path)
    codes = {f["code"] for f in result["findings"] if f["severity"] == "BLOCKER"}
    assert "SPEC_OUTSIDE_FEATURE_DOCS" not in codes
    assert any(f["code"] == "SPEC_OUTSIDE_FEATURE_DOCS" for f in result["findings"])


def test_canonical_block_redirects_spec_output_to_feature_docs():
    text = (adm.skill_root() / adm.CANONICAL_GUIDELINES_REL).read_text(encoding="utf-8")
    assert "docs/superpowers/specs/" in text
    assert "single source of truth" in text
    # The redirect must survive edits to the block: both the override statement and the
    # shape mapping are what stop an agent from writing a standalone design doc.
    assert "overrides any skill default" in text
    assert "Brainstorm output → feature doc" in text
