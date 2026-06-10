#!/usr/bin/env python3
"""Declarative per-agent profiles: delivery adapters over the agnostic core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentProfile:
    """Describes how the canonical method is *delivered* for one AI agent.

    A profile customizes delivery only — never the docs model or the method.
    """

    key: str
    soft_target: str  # path of the strongest always-on instruction surface
    skill_install: str | None  # where the skill package is installed, if hosted
    native_hard_gate: str | None  # the agent's own blocking primitive, if any
    detect_dirs: tuple[str, ...]  # filesystem markers implying this agent is in use
    soft_wrapper: str | None = None  # e.g. "mdc" for Cursor rule frontmatter


PROFILES: dict[str, AgentProfile] = {
    "claude": AgentProfile(
        key="claude",
        soft_target="CLAUDE.md",
        skill_install=".claude/skills/plan-docs-standardization/",
        native_hard_gate="claude-hooks",
        detect_dirs=(".claude",),
    ),
    "cursor": AgentProfile(
        key="cursor",
        soft_target=".cursor/rules/docs-first.mdc",
        skill_install=".cursor/skills/plan-docs-standardization/",
        native_hard_gate=None,
        detect_dirs=(".cursor",),
        soft_wrapper="mdc",
    ),
    "codex": AgentProfile(
        key="codex",
        soft_target="AGENTS.md",
        skill_install=".agents/skills/plan-docs-standardization/",
        native_hard_gate="codex-hooks",
        detect_dirs=(".codex", ".agents"),
    ),
    "generic": AgentProfile(
        key="generic",
        soft_target="AGENTS.md",
        skill_install=None,
        native_hard_gate=None,
        detect_dirs=(),
    ),
}


def get_profile(key: str) -> AgentProfile:
    return PROFILES[key]


def detect_signal_profiles(repo: Path) -> list[str]:
    """Profile keys whose filesystem markers exist in the repo, sorted.

    `generic` has no marker and is never auto-detected.
    """

    repo = Path(repo)
    detected = [
        profile.key
        for profile in PROFILES.values()
        if profile.detect_dirs
        and any((repo / marker).is_dir() for marker in profile.detect_dirs)
    ]
    return sorted(detected)
