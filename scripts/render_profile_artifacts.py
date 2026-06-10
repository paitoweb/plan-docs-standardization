#!/usr/bin/env python3
"""Generate per-agent soft-layer artifacts from the single canonical block.

Single source of truth: assets/templates/ai-instructions/guidelines.en.md.
Per-agent variation is delivery-only (e.g. Cursor .mdc frontmatter).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_profiles as ap
import audit_docs_model as adm

CURSOR_FRONTMATTER = (
    "---\n"
    "description: Docs-First workflow and working principles (always applied)\n"
    "alwaysApply: true\n"
    "---\n"
)


def render_soft_block() -> str:
    """The agnostic always-on block = the canonical guidelines file, verbatim."""

    path = adm.skill_root() / adm.CANONICAL_GUIDELINES_REL
    return path.read_text(encoding="utf-8").strip() + "\n"


def render_for_profile(profile_key: str) -> str:
    profile = ap.get_profile(profile_key)
    block = render_soft_block()
    if profile.soft_wrapper == "mdc":
        return CURSOR_FRONTMATTER + "\n" + block
    return block
