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
