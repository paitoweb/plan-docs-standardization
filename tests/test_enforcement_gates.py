import json

import enforcement_gates as eg


def test_default_audit_cmd_runs_the_audit_script():
    assert "audit_docs_model.py" in eg.DEFAULT_AUDIT_CMD


def test_ci_workflow_contains_audit_cmd_and_triggers():
    yml = eg.render_ci_workflow("python3 audit.py .")
    assert "name: Docs-First Audit" in yml
    assert "pull_request" in yml
    assert "python3 audit.py ." in yml
    assert yml.endswith("\n")


def test_precommit_hook_blocks_on_nonzero_and_is_sh():
    hook = eg.render_precommit_hook("python3 audit.py .")
    assert hook.startswith("#!/bin/sh")
    assert "python3 audit.py ." in hook
    assert "exit 1" in hook  # blocks the commit on failure
    assert "--no-verify" in hook  # tells the user how to bypass deliberately


def test_claude_hooks_is_valid_json_with_stop_event():
    text = eg.render_claude_hooks("python3 audit.py .")
    data = json.loads(text)
    assert "hooks" in data
    assert "Stop" in data["hooks"]
    # the audit command is wired into a command hook
    assert "python3 audit.py ." in text


def test_codex_hooks_is_valid_json_with_pretooluse_deny():
    text = eg.render_codex_hooks("python3 audit.py .")
    data = json.loads(text)
    assert "PreToolUse" in data["hooks"]
    matcher_group = data["hooks"]["PreToolUse"][0]
    assert "matcher" in matcher_group
    assert "python3 audit.py ." in text


def test_gate_present_ci(tmp_path):
    assert eg.gate_present(tmp_path, "ci") is False
    wf = tmp_path / ".github" / "workflows" / "docs-audit.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: x\n", encoding="utf-8")
    assert eg.gate_present(tmp_path, "ci") is True


def test_gate_present_local_hook(tmp_path):
    hook = tmp_path / ".githooks" / "pre-commit"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    assert eg.gate_present(tmp_path, "local-hook") is True


def test_gate_present_claude_requires_hooks_marker(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"model": "x"}', encoding="utf-8")
    assert eg.gate_present(tmp_path, "claude-hooks") is False  # no "hooks" key
    settings.write_text('{"hooks": {}}', encoding="utf-8")
    assert eg.gate_present(tmp_path, "claude-hooks") is True


def test_gate_present_codex(tmp_path):
    assert eg.gate_present(tmp_path, "codex-hooks") is False
    hooks = tmp_path / ".codex" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text("{}", encoding="utf-8")
    assert eg.gate_present(tmp_path, "codex-hooks") is True


def test_gate_present_unknown_is_false(tmp_path):
    assert eg.gate_present(tmp_path, "telepathy") is False
