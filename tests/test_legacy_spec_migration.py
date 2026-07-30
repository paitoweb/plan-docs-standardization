"""Migrating a legacy design doc: structure proposed, content derived from the code.

The spec is a lead, not a source. A dated design doc drifts from the implementation, so
transcribing it would launder stale claims into the one place that must not lie.
"""

import audit_docs_model as adm
import build_docs_alignment_plan as plan


def _feature(tmp_path, slug, files=None):
    feature_dir = tmp_path / "docs" / "features" / slug
    feature_dir.mkdir(parents=True)
    for name in ("README.md", "flows.md", "rules.md", "notes.md"):
        body = (files or {}).get(name, f"# {slug}\n")
        (feature_dir / name).write_text(body, encoding="utf-8")
    return feature_dir


def _spec(tmp_path, filename):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / filename).write_text("# design\n", encoding="utf-8")


def test_candidate_slug_strips_date_and_design_suffix():
    assert (
        adm.spec_to_candidate_slug("2026-06-09-voice-transcription-design.md")
        == "voice-transcription"
    )
    assert adm.spec_to_candidate_slug("file-tree.md") == "file-tree"


def test_unverified_marker_is_reported_once_per_feature(tmp_path):
    _feature(
        tmp_path,
        "voice",
        {
            "README.md": f"# voice\n\nREQ-VOICE-001 {adm.UNVERIFIED_MARKER}\n",
            "rules.md": f"rule a {adm.UNVERIFIED_MARKER}\nrule b {adm.UNVERIFIED_MARKER}\n",
        },
    )
    findings = []
    adm.check_unverified_claims(tmp_path, findings)

    assert len(findings) == 1
    assert findings[0].code == "FEATURE_DOC_UNVERIFIED"
    assert findings[0].severity == "WARN"
    assert findings[0].path == "docs/features/voice"
    assert "3 claim(s)" in findings[0].message


def test_feature_without_markers_is_silent(tmp_path):
    _feature(tmp_path, "voice")
    findings = []
    adm.check_unverified_claims(tmp_path, findings)
    assert findings == []


def test_unverified_never_blocks(tmp_path):
    """Blocking would force whole-feature verification before anything can land."""

    _feature(tmp_path, "voice", {"README.md": f"x {adm.UNVERIFIED_MARKER}\n"})
    result = adm.audit_repository(tmp_path)
    blockers = {f["code"] for f in result["findings"] if f["severity"] == "BLOCKER"}
    assert "FEATURE_DOC_UNVERIFIED" not in blockers
    assert any(f["code"] == "FEATURE_DOC_UNVERIFIED" for f in result["findings"])


def test_migration_lists_specs_without_a_feature_doc(tmp_path):
    _spec(tmp_path, "2026-06-09-voice-transcription-design.md")
    entries = plan.legacy_spec_migration(tmp_path)

    assert len(entries) == 1
    assert entries[0]["slug"] == "voice-transcription"
    assert entries[0]["spec"].endswith("2026-06-09-voice-transcription-design.md")
    assert entries[0]["targets"] == [
        "docs/features/voice-transcription/README.md",
        "docs/features/voice-transcription/flows.md",
        "docs/features/voice-transcription/rules.md",
        "docs/features/voice-transcription/notes.md",
    ]


def test_already_migrated_spec_is_skipped(tmp_path):
    _spec(tmp_path, "2026-06-09-voice-transcription-design.md")
    _feature(tmp_path, "voice-transcription")
    assert plan.legacy_spec_migration(tmp_path) == []


def test_already_migrated_match_ignores_naming_convention(tmp_path):
    _spec(tmp_path, "2026-06-09-voice-transcription-design.md")
    _feature(tmp_path, "voiceTranscription")
    assert plan.legacy_spec_migration(tmp_path) == []


def test_repo_without_specs_yields_no_migration(tmp_path):
    (tmp_path / "docs").mkdir()
    assert plan.legacy_spec_migration(tmp_path) == []


def test_migration_section_is_rendered_with_the_procedure(tmp_path):
    _spec(tmp_path, "2026-06-09-voice-transcription-design.md")
    migration = plan.legacy_spec_migration(tmp_path)
    result = adm.audit_repository(tmp_path)

    markdown = plan.build_markdown(tmp_path, result, [], [], [], [], migration)

    assert "Legacy Spec Migration (spec is the lead, code is the source)" in markdown
    assert "Read the implementation" in markdown
    assert adm.UNVERIFIED_MARKER in markdown
    assert "docs/features/voice-transcription/README.md" in markdown
    assert "candidate" in markdown


def test_migration_section_absent_when_there_is_nothing_to_migrate(tmp_path):
    (tmp_path / "docs").mkdir()
    result = adm.audit_repository(tmp_path)
    markdown = plan.build_markdown(tmp_path, result, [], [], [], [], [])
    assert "Legacy Spec Migration" not in markdown


def test_migration_targets_are_deferred_never_created(tmp_path):
    """Content not read against the code is exactly the laundering the guardrail prevents."""

    _spec(tmp_path, "2026-06-09-voice-transcription-design.md")
    output = _run_plan(tmp_path)

    deferred = {item["path"] for item in output["deferred_create_files"]}
    assert "docs/features/voice-transcription/README.md" in deferred
    assert not any(
        d["path"].startswith("docs/features/voice-transcription/") for d in output["diffs"]
    )
    reasons = {
        item["reason"]
        for item in output["deferred_create_files"]
        if item["path"].startswith("docs/features/voice-transcription/")
    }
    assert reasons == {plan.MIGRATION_DEFERRED_REASON}


def _run_plan(repo):
    import json
    import subprocess
    from pathlib import Path

    script = Path(plan.__file__)
    completed = subprocess.run(
        ["python3", str(script), str(repo), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(completed.stdout)
