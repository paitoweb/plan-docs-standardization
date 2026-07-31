"""The canonical block is copied into consumer repos, so copies go stale silently.

Every structural rule keeps passing on a block that is two revisions old — which is how a
repo that installed the block correctly ends up running guidelines from months ago.
"""

import audit_docs_model as adm
import build_docs_alignment_plan as plan
import render_profile_artifacts as rpa


def _block(version=None, workflow_extra=""):
    marker = f"<!-- docs-first-block: {version} -->\n\n" if version is not None else ""
    return (
        "See [docs/index.md](docs/index.md).\n\n"
        f"## Workflow: New Feature\n\n{marker}"
        f"1. Brainstorm\n2. Feature doc in `docs/features/<f>/`\n3. Plan\n{workflow_extra}\n"
        "## Working Principles\n\n- a\n- b\n- c\n"
    )


def _claude(tmp_path, text):
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    return [f for f in findings if f.path == "CLAUDE.md"]


def test_current_version_is_clean(tmp_path):
    assert _claude(tmp_path, _block(adm.CANONICAL_BLOCK_VERSION)) == []


def test_older_version_warns(tmp_path):
    findings = _claude(tmp_path, _block(adm.CANONICAL_BLOCK_VERSION - 1))
    assert [(f.severity, f.code) for f in findings] == [
        ("WARN", "AI_INSTRUCTION_BLOCK_STALE")
    ]
    assert str(adm.CANONICAL_BLOCK_VERSION) in findings[0].message


def test_missing_marker_is_info_not_warn(tmp_path):
    """Every repo alive today is unmarked; a WARN would spam all of them at once."""

    findings = _claude(tmp_path, _block(None))
    assert [(f.severity, f.code) for f in findings] == [
        ("INFO", "AI_INSTRUCTION_BLOCK_UNVERSIONED")
    ]
    assert "translation" in findings[0].message


def test_newer_version_points_at_the_skill_not_the_repo(tmp_path):
    findings = _claude(tmp_path, _block(adm.CANONICAL_BLOCK_VERSION + 1))
    assert [(f.severity, f.code) for f in findings] == [
        ("INFO", "AI_INSTRUCTION_BLOCK_AHEAD")
    ]
    assert "update the skill" in findings[0].message


def test_version_is_not_reported_when_the_block_is_absent(tmp_path):
    """We are already telling them to install the block; its version is not the news."""

    findings = _claude(tmp_path, "# nothing structural\n")
    codes = {f.code for f in findings}
    assert "AI_INSTRUCTION_SECTION_MISSING" in codes
    assert not any(code.startswith("AI_INSTRUCTION_BLOCK_") for code in codes)


def test_marker_parsing_tolerates_spacing():
    assert adm.installed_block_version("<!--docs-first-block:7-->") == 7
    assert adm.installed_block_version("<!--   docs-first-block:  7   -->") == 7
    assert adm.installed_block_version("no marker here") is None


def test_marker_ships_inside_the_installed_sections():
    """A marker in the preamble would never reach a consumer: the skill installs the block
    by appending the two sections, so anything above them is dropped."""

    workflow = adm.load_canonical_sections()["## Workflow: New Feature"]
    assert adm.installed_block_version(workflow) == adm.CANONICAL_BLOCK_VERSION


def test_marker_survives_profile_rendering():
    for profile in ("claude", "cursor", "codex", "generic"):
        rendered = rpa.render_for_profile(profile)
        assert adm.installed_block_version(rendered) == adm.CANONICAL_BLOCK_VERSION


def test_marker_does_not_disturb_shape_detection():
    text = _block(adm.CANONICAL_BLOCK_VERSION)
    assert adm.detect_ai_instruction_shapes(text) == (True, True)
    assert adm.workflow_routes_through_feature_docs(text)


def test_plan_tells_a_stale_file_what_to_do_instead_of_no_changes(tmp_path):
    """"No changes required." on a stale block is precisely how it stayed stale."""

    (tmp_path / "CLAUDE.md").write_text(
        _block(adm.CANONICAL_BLOCK_VERSION - 1), encoding="utf-8"
    )
    message = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "No changes required." not in message
    assert "render_profile_artifacts.py" in message
    assert "appending would duplicate" in message


def test_plan_reports_no_changes_for_a_current_block(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        _block(adm.CANONICAL_BLOCK_VERSION), encoding="utf-8"
    )
    assert plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md") == "No changes required."
