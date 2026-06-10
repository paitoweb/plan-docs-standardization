#!/usr/bin/env python3
"""Render and detect deterministic enforcement-gate artifacts.

A gate runs the docs audit at a fixed point in the workflow. All gates share one
`audit_cmd`. This module never imports audit_docs_model (which imports this one).
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_AUDIT_CMD = "python3 scripts/audit_docs_model.py ."


def render_ci_workflow(audit_cmd: str = DEFAULT_AUDIT_CMD) -> str:
    return (
        "name: Docs-First Audit\n"
        "on:\n"
        "  pull_request:\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  docs-audit:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.x'\n"
        "      - name: Run docs audit (fails on BLOCKERs)\n"
        f"        run: {audit_cmd}\n"
    )


def render_precommit_hook(audit_cmd: str = DEFAULT_AUDIT_CMD) -> str:
    return (
        "#!/bin/sh\n"
        "# Docs-First gate: block commits that fail the docs audit.\n"
        f"{audit_cmd}\n"
        "status=$?\n"
        'if [ "$status" -ne 0 ]; then\n'
        '  echo "Docs-First audit failed (exit $status). Fix BLOCKERs, '
        'or use git commit --no-verify to bypass deliberately." >&2\n'
        "  exit 1\n"
        "fi\n"
    )
