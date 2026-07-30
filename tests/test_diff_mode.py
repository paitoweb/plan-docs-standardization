"""--diff mode: shipping code while touching no feature doc is a BLOCKER.

The audit is otherwise blind to code, so a feature can ship fully implemented and fully
undocumented with every rule passing. This is the cheap PR-time backstop.
"""

import subprocess

import audit_docs_model as adm


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def _commit(repo, files: dict[str, str], message="change"):
    for rel, body in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _run(repo, base="main"):
    findings = []
    adm.check_diff_feature_docs(repo, findings, base)
    return findings


def test_code_without_feature_doc_blocks(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/voice.ts": "export const x = 1\n"})

    findings = _run(repo)
    assert [f.code for f in findings] == ["DIFF_CODE_WITHOUT_FEATURE_DOC"]
    assert findings[0].severity == "BLOCKER"
    assert "src/voice.ts" in findings[0].message


def test_code_with_feature_doc_passes(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(
        repo,
        {
            "src/voice.ts": "export const x = 1\n",
            "docs/features/voice/README.md": "# voice\n",
        },
    )
    assert _run(repo) == []


def test_test_only_change_is_exempt_by_default(tmp_path):
    """A test-only change ships no behavior, so flagging it would be a false positive."""

    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"tests/voice_test.py": "def test_x():\n    pass\n"})
    assert _run(repo) == []


def test_colocated_test_file_is_exempt(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/voice.test.ts": "it('x', () => {})\n"})
    assert _run(repo) == []


def test_non_code_change_is_ignored(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"README.md": "# hi\n", "package.json": "{}\n"})
    assert _run(repo) == []


def test_skip_marker_in_any_commit_of_the_range_exempts(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/a.ts": "1\n"}, message="refactor\n\ndocs-first: skip")
    _commit(repo, {"src/b.ts": "2\n"}, message="more refactor")
    assert _run(repo) == []


def test_unresolvable_base_warns_and_never_blocks(tmp_path):
    """Failing a pipeline because a ref is missing punishes the wrong mistake."""

    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/a.ts": "1\n"})

    findings = _run(repo, base="origin/does-not-exist")
    assert [f.code for f in findings] == ["DIFF_BASE_UNRESOLVED"]
    assert findings[0].severity == "WARN"


def test_empty_diff_produces_nothing(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    assert _run(repo) == []


def test_config_globs_extend_rather_than_replace_the_defaults(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".docs-first").mkdir()
    (repo / ".docs-first" / "config.yml").write_text(
        "diff_exempt_globs: [generated/*]\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "config")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"generated/client.ts": "1\n", "tests/a_test.py": "pass\n"})

    # `generated/` comes from config, `tests/` from the defaults: both must apply.
    assert _run(repo) == []


def test_config_code_extensions_replace_the_default_set(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".docs-first").mkdir()
    (repo / ".docs-first" / "config.yml").write_text(
        "code_extensions: [.erl]\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "config")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/a.ts": "1\n"})
    assert _run(repo) == []  # .ts is no longer code for this repo

    _commit(repo, {"src/b.erl": "-module(b).\n"})
    assert [f.code for f in _run(repo)] == ["DIFF_CODE_WITHOUT_FEATURE_DOC"]


def test_diff_check_runs_only_when_requested(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, {"src/a.ts": "1\n"})

    without = adm.audit_repository(repo)
    assert not any(f["code"].startswith("DIFF_") for f in without["findings"])

    with_diff = adm.audit_repository(repo, diff_base="main")
    assert any(f["code"] == "DIFF_CODE_WITHOUT_FEATURE_DOC" for f in with_diff["findings"])


def test_ci_workflow_fetches_full_history_for_the_diff_base():
    """Shallow clone is actions/checkout's default; origin/main would not resolve."""

    import enforcement_gates as eg

    workflow = eg.render_ci_workflow()
    assert "fetch-depth: 0" in workflow
