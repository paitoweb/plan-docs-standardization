# Agent Profiles — Soft Layer & Generator (Plan 2 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate each agent's always-on instruction artifact from the single canonical block, ship the Cursor rule template guarded by an anti-drift test, and make the audit check each active profile's soft target.

**Architecture:** A new generator module `scripts/render_profile_artifacts.py` renders the soft-layer content per profile — the canonical block verbatim for plain targets (CLAUDE.md / AGENTS.md), wrapped in `.mdc` frontmatter for Cursor. The committed Cursor template is the generator's output, and a test asserts they stay equal (the structural fix for the PR #4 drift class). The audit's AI-instruction check becomes profile-aware: active profiles' soft targets join the checked set, so Cursor's `.mdc` is validated structurally exactly like `CLAUDE.md`.

**Tech Stack:** Python 3 (stdlib only), pytest. Builds on Plan 1's `agent_profiles` module (`PROFILES`, `get_profile`, `resolve_active_profiles`).

**Spec:** `docs/superpowers/specs/2026-06-10-agent-profiles-and-enforcement-design.md` (§6 soft layer, §9 single-source & anti-drift).

**Phasing note:** This plan merges the spec's "soft layer" and "generator/anti-drift" work, because single-source generation *is* the soft-layer mechanism. Plan 3 covers install/plan-builder integration and the skill's detect→ask→persist UX; Plan 4 covers the hard layer (gates).

**Single source:** `assets/templates/ai-instructions/guidelines.en.md` (sections `## Workflow: New Feature`, `## Working Principles`, `## Documentation Map`). No per-agent prose is ever hand-written.

---

## File Structure

- **Create** `scripts/render_profile_artifacts.py` — `render_soft_block`, `render_for_profile`, `CURSOR_FRONTMATTER`, CLI `main`.
- **Create** `assets/templates/cursor/rules/docs-first.mdc` — generated Cursor rule (frontmatter + canonical block).
- **Modify** `scripts/audit_docs_model.py` — add `ai_instruction_targets`; make `check_ai_instruction_files` iterate it.
- **Create** `tests/test_render_profile_artifacts.py` — generator + anti-drift tests.
- **Create** `tests/test_soft_layer_audit.py` — profile-aware AI-instruction check tests.

---

## Task 1: Render the canonical soft block

**Files:**
- Create: `scripts/render_profile_artifacts.py`
- Test: `tests/test_render_profile_artifacts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_profile_artifacts.py
import render_profile_artifacts as rpa


def test_soft_block_contains_canonical_sections():
    block = rpa.render_soft_block()
    assert "## Workflow: New Feature" in block
    assert "## Working Principles" in block
    assert "## Documentation Map" in block


def test_soft_block_links_docs_index():
    # The Documentation Map section points at docs/index.md; must survive into the block.
    assert "docs/index.md" in rpa.render_soft_block()


def test_soft_block_ends_with_single_newline():
    block = rpa.render_soft_block()
    assert block.endswith("\n")
    assert not block.endswith("\n\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'render_profile_artifacts'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/render_profile_artifacts.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/render_profile_artifacts.py tests/test_render_profile_artifacts.py
git commit -m "feat: render canonical soft block from guidelines.en.md"
```

---

## Task 2: Render per-profile (Cursor frontmatter wrapper)

**Files:**
- Modify: `scripts/render_profile_artifacts.py` (add `render_for_profile`)
- Test: `tests/test_render_profile_artifacts.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_render_profile_artifacts.py


def test_plain_profiles_return_bare_block():
    block = rpa.render_soft_block()
    assert rpa.render_for_profile("claude") == block
    assert rpa.render_for_profile("codex") == block
    assert rpa.render_for_profile("generic") == block


def test_cursor_profile_wraps_block_in_mdc_frontmatter():
    out = rpa.render_for_profile("cursor")
    assert out.startswith("---\n")
    assert "alwaysApply: true" in out
    assert "## Workflow: New Feature" in out  # block content preserved
    # frontmatter then a blank line then the block
    assert out.startswith(rpa.CURSOR_FRONTMATTER + "\n")
    assert out.endswith(rpa.render_soft_block())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -k profile -v`
Expected: FAIL with `AttributeError: module 'render_profile_artifacts' has no attribute 'render_for_profile'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/render_profile_artifacts.py


def render_for_profile(profile_key: str) -> str:
    profile = ap.get_profile(profile_key)
    block = render_soft_block()
    if profile.soft_wrapper == "mdc":
        return CURSOR_FRONTMATTER + "\n" + block
    return block
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/render_profile_artifacts.py tests/test_render_profile_artifacts.py
git commit -m "feat: render per-profile soft artifact (Cursor .mdc wrapper)"
```

---

## Task 3: CLI entry point for regeneration

**Files:**
- Modify: `scripts/render_profile_artifacts.py` (add `main`)
- Test: `tests/test_render_profile_artifacts.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_render_profile_artifacts.py
import subprocess
import sys
from pathlib import Path


def test_cli_prints_profile_artifact():
    script = Path(__file__).resolve().parent.parent / "scripts" / "render_profile_artifacts.py"
    result = subprocess.run(
        [sys.executable, str(script), "cursor"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == rpa.render_for_profile("cursor")


def test_cli_rejects_unknown_profile():
    script = Path(__file__).resolve().parent.parent / "scripts" / "render_profile_artifacts.py"
    result = subprocess.run(
        [sys.executable, str(script), "windsurf"], capture_output=True, text=True
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -k cli -v`
Expected: FAIL — `argparse` not wired; `SystemExit`/no `main`, so `subprocess` output won't match.

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/render_profile_artifacts.py


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render per-agent soft-layer artifact")
    parser.add_argument("profile", choices=sorted(ap.PROFILES))
    args = parser.parse_args(argv)
    sys.stdout.write(render_for_profile(args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/render_profile_artifacts.py tests/test_render_profile_artifacts.py
git commit -m "feat: add render_profile_artifacts CLI for regeneration"
```

---

## Task 4: Commit the generated Cursor rule + anti-drift guard

**Files:**
- Create: `assets/templates/cursor/rules/docs-first.mdc` (generated output)
- Test: `tests/test_render_profile_artifacts.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_render_profile_artifacts.py


def test_committed_cursor_rule_matches_generator():
    repo_root = Path(__file__).resolve().parent.parent
    committed = repo_root / "assets" / "templates" / "cursor" / "rules" / "docs-first.mdc"
    assert committed.exists(), "Cursor rule template is missing; regenerate it."
    assert committed.read_text(encoding="utf-8") == rpa.render_for_profile("cursor"), (
        "Cursor rule drifted from canonical. Regenerate:\n"
        "  python3 scripts/render_profile_artifacts.py cursor "
        "> assets/templates/cursor/rules/docs-first.mdc"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -k committed -v`
Expected: FAIL — file does not exist yet (`assert committed.exists()`).

- [ ] **Step 3: Generate the committed artifact**

Run exactly (from repo root):

```bash
mkdir -p assets/templates/cursor/rules
python3 scripts/render_profile_artifacts.py cursor > assets/templates/cursor/rules/docs-first.mdc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_render_profile_artifacts.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add assets/templates/cursor/rules/docs-first.mdc tests/test_render_profile_artifacts.py
git commit -m "feat: ship generated Cursor rule with anti-drift test"
```

---

## Task 5: Make the audit's AI-instruction check profile-aware

**Files:**
- Modify: `scripts/audit_docs_model.py` (add `ai_instruction_targets`; use it in `check_ai_instruction_files`)
- Test: `tests/test_soft_layer_audit.py`

Context: `check_ai_instruction_files` currently iterates the flat `AI_INSTRUCTION_FILES`. It will iterate `ai_instruction_targets(repo)` = the flat list plus active profiles' `soft_target`s (deduped). `_ap` (agent_profiles) is already imported in `audit_docs_model.py` from Plan 1. Active profiles come from `_ap.resolve_active_profiles(repo)`, which uses config → filesystem signals.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_soft_layer_audit.py
import audit_docs_model as adm


def _codes_for(findings, path):
    return {f.code for f in findings if f.path == path}


def test_cursor_rule_not_checked_when_cursor_inactive(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    paths = {f.path for f in findings}
    assert ".cursor/rules/docs-first.mdc" not in paths


def test_cursor_rule_absent_reports_info_when_cursor_active(tmp_path):
    (tmp_path / ".cursor").mkdir()  # signal -> cursor profile active
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert _codes_for(findings, ".cursor/rules/docs-first.mdc") == {"AI_INSTRUCTION_FILE_ABSENT"}


def test_cursor_rule_present_but_empty_blocks_when_active(tmp_path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "docs-first.mdc").write_text(
        "---\nalwaysApply: true\n---\n\n# nothing structural here\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert "AI_INSTRUCTION_SECTION_MISSING" in _codes_for(
        findings, ".cursor/rules/docs-first.mdc"
    )


def test_targets_helper_dedupes_agents_md(tmp_path):
    (tmp_path / ".codex").mkdir()  # codex soft_target is AGENTS.md, already in base list
    targets = adm.ai_instruction_targets(tmp_path)
    assert targets.count("AGENTS.md") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_soft_layer_audit.py -v`
Expected: FAIL — `AttributeError: module 'audit_docs_model' has no attribute 'ai_instruction_targets'` (and the cursor `.mdc` is not yet checked).

- [ ] **Step 3: Write minimal implementation**

Add the helper just above `check_ai_instruction_files` in `scripts/audit_docs_model.py`:

```python
def ai_instruction_targets(repo: Path) -> list[str]:
    """Flat AI-instruction files plus each active profile's soft target (deduped)."""

    targets = list(AI_INSTRUCTION_FILES)
    active, _source = _ap.resolve_active_profiles(repo)
    for key in active:
        soft_target = _ap.PROFILES[key].soft_target
        if soft_target not in targets:
            targets.append(soft_target)
    return targets
```

Then change the loop header in `check_ai_instruction_files` from:

```python
def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
    for rel in AI_INSTRUCTION_FILES:
```

to:

```python
def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
    for rel in ai_instruction_targets(repo):
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python3 -m pytest tests/test_soft_layer_audit.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite (no regression)**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — all prior tests (Plan 1 + baseline) plus the new ones, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_soft_layer_audit.py
git commit -m "feat: check active profiles' soft targets in AI-instruction audit"
```

---

## Self-Review

**Spec coverage (Plan 2 portion):**
- §6 soft layer — strongest always-on surface per agent → Tasks 1–2 (generator) + Task 5 (audit checks each active profile's surface).
- §9 single-source & anti-drift → Tasks 1–4 (generator + committed artifact + drift test).
- §6 "lean Codex variant (32 KiB)" → **not needed yet**: `guidelines.en.md` is ~30 lines, far under 32 KiB. Documented as a future refinement; no separate variant in this plan.

**Deferred (correctly) to later plans:**
- Plan-builder proposing per-active-profile diffs, skill detect→ask→persist UX, config write-on-consent, multi-profile install, SKILL.md/README docs → Plan 3.
- Hard layer (CI/local/native gates) + enforcement reconciliation → Plan 4.

**Placeholder scan:** none — every code/test step is complete.

**Type consistency:** `render_soft_block`/`render_for_profile`/`CURSOR_FRONTMATTER`/`main` consistent across Tasks 1–4; `ai_instruction_targets` defined in Task 5 and used by `check_ai_instruction_files`; reuses Plan 1 names `_ap.PROFILES`, `_ap.resolve_active_profiles`, `AgentProfile.soft_target`, `AgentProfile.soft_wrapper` exactly.

---

## Next Plans (not in this file)
- **Plan 3 — Install path & skill UX:** plan-builder proposes per-active-profile soft-target diffs; the skill's detect→ask→persist flow; `.docs-first/config.yml` write-on-consent; multi-profile composition; SKILL.md + README documentation.
- **Plan 4 — Hard layer & enforcement:** CI workflow + branch-protection helper, local `core.hooksPath` hook, Claude/Codex native hooks, the consent flow, and §5.4 enforcement-drift reconciliation in the audit.
