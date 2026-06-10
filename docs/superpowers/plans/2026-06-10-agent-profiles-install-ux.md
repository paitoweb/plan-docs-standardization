# Agent Profiles — Install Path & Skill UX (Plan 3 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make per-agent soft-layer delivery *visible*: the alignment plan proposes diffs for each active profile's soft target, the skill can persist the user's choices on consent, and SKILL.md documents the detect → ask → persist → install flow (incl. multiple agents in one repo).

**Architecture:** Three pieces. (1) The plan builder's "alter" routing becomes profile-aware — it reuses the audit's `ai_instruction_targets(repo)` so an active Cursor `.mdc` (or any active profile's surface) routes through the canonical-block diff. (2) A `save_config(repo, cfg)` write-on-consent primitive in `docs_first_config.py` (the only mutation, used only when the user agrees). (3) SKILL.md gains an "Agent Profiles" section codifying detection, asking when undetermined, persisting decisions, the install offer, and multi-profile composition — pure orchestration prose; the scripts stay the primitives.

**Tech Stack:** Python 3 (stdlib only), pytest. Builds on Plan 1 (`agent_profiles`, `docs_first_config`) and Plan 2 (`ai_instruction_targets`, `render_profile_artifacts`).

**Spec:** `docs/superpowers/specs/2026-06-10-agent-profiles-and-enforcement-design.md` (§5.3 lifecycle write-on-consent, §6 soft layer delivery, §8 runtime model, §3 multi-profile).

**Phasing note:** Plan 4 (hard layer / gates) is separate. This plan does not touch enforcement gates.

---

## File Structure

- **Modify** `scripts/build_docs_alignment_plan.py` — make `proposed_diffs` route AI-instruction diffs via `adm.ai_instruction_targets(repo)` (repo-aware) instead of a static module set.
- **Modify** `scripts/docs_first_config.py` — add `save_config(repo, cfg)`.
- **Modify** `SKILL.md` — add `## Agent Profiles` section; extend the AI-instruction bullet.
- **Modify** `references/compliance-rules.md` — document agent profiles, `.docs-first/config.yml`, and the `DOCS_FIRST_CONFIG_INVALID` code.
- **Create** `tests/test_profile_plan.py` — profile-aware alter-routing test.
- **Modify** `tests/test_docs_first_config.py` — append `save_config` tests.

---

## Task 1: Profile-aware alter routing in the plan builder

**Files:**
- Modify: `scripts/build_docs_alignment_plan.py`
- Test: `tests/test_profile_plan.py`

Context: `proposed_diffs(repo, result, create_files, alter_files, max_diffs)` currently routes a file to `ai_instruction_update_diff` when `target_rel in AI_INSTRUCTION_FILES` (a static module-level set built from `adm.AI_INSTRUCTION_FILES`). We replace that membership test with the repo-aware `adm.ai_instruction_targets(repo)` (added in Plan 2), so an active profile's soft target — e.g. `.cursor/rules/docs-first.mdc` when `.cursor/` exists — routes through the canonical-block diff. The static module constant `AI_INSTRUCTION_FILES` (line ~26) becomes dead and is removed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile_plan.py
import build_docs_alignment_plan as plan


def test_proposed_diff_routes_active_cursor_rule_through_canonical_block(tmp_path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    rel = ".cursor/rules/docs-first.mdc"
    # present but missing the structural sections -> a BLOCKER the audit would raise
    (tmp_path / rel).write_text("---\nalwaysApply: true\n---\n\n# empty\n", encoding="utf-8")

    result = {
        "findings": [
            {
                "code": "AI_INSTRUCTION_SECTION_MISSING",
                "path": rel,
                "severity": "BLOCKER",
                "message": "missing workflow section",
            }
        ]
    }
    items, _deferred = plan.proposed_diffs(tmp_path, result, [], [rel], max_diffs=30)
    cursor_items = [i for i in items if i["path"] == rel]
    assert len(cursor_items) == 1
    assert cursor_items[0]["type"] == "update"
    # the canonical block is what gets appended
    assert "## Workflow: New Feature" in cursor_items[0]["diff"]


def test_inactive_cursor_rule_not_treated_as_ai_instruction(tmp_path):
    # no .cursor/ dir -> cursor profile inactive -> the path falls through to update-plan
    rel = ".cursor/rules/docs-first.mdc"
    result = {
        "findings": [
            {"code": "SOME_OTHER", "path": rel, "severity": "BLOCKER", "message": "x"}
        ]
    }
    items, _deferred = plan.proposed_diffs(tmp_path, result, [], [rel], max_diffs=30)
    assert items[0]["type"] == "update-plan"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_profile_plan.py -v`
Expected: FAIL — `test_proposed_diff_routes_active_cursor_rule_through_canonical_block` gets `update-plan` (the generic fallback) instead of `update`, because the static set does not contain the `.mdc`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/build_docs_alignment_plan.py`, delete the dead module constant:

```python
IGNORE_ACTION_CODES = {"AI_INSTRUCTION_FILE_ABSENT"}
AI_INSTRUCTION_FILES = set(adm.AI_INSTRUCTION_FILES)
```

becomes:

```python
IGNORE_ACTION_CODES = {"AI_INSTRUCTION_FILE_ABSENT"}
```

Then inside `proposed_diffs`, just before the `for target_rel in alter_files:` loop, compute the repo-aware set:

```python
    ai_instruction_targets = set(adm.ai_instruction_targets(repo))
    feature_gaps = adm.compute_feature_section_gaps(repo)
```

(`feature_gaps` already exists on that line — add the `ai_instruction_targets` line right above it.)

And change the routing test inside the loop from:

```python
        if target_rel in AI_INSTRUCTION_FILES:
```

to:

```python
        if target_rel in ai_instruction_targets:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_profile_plan.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite (no regression)**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — all prior tests still green (the existing `CLAUDE.md`/`AGENTS.md` routing still works because they are in `ai_instruction_targets` via the base flat list).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_docs_alignment_plan.py tests/test_profile_plan.py
git commit -m "feat: route active profiles' soft targets through canonical-block diff"
```

---

## Task 2: `save_config` write-on-consent primitive

**Files:**
- Modify: `scripts/docs_first_config.py`
- Test: `tests/test_docs_first_config.py` (append)

Context: This is the only mutation the agent-profile feature performs, and per §5.3 it runs **only on explicit user consent** (the skill previews `render_config(cfg)` first). The function just writes; the consent/preview is the skill's responsibility (Task 3 prose).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_docs_first_config.py


def test_save_config_creates_dir_and_file(tmp_path):
    cfg = dfc.DocsFirstConfig(profiles=["cursor"], enforcement_chosen=["ci"], updated="2026-06-10")
    path = dfc.save_config(tmp_path, cfg)
    assert path == tmp_path / dfc.CONFIG_REL
    assert path.exists()
    assert (tmp_path / ".docs-first").is_dir()


def test_save_config_round_trips_through_load(tmp_path):
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "codex"],
        enforcement_chosen=["local-hook"],
        enforcement_declined=["ci"],
        updated="2026-06-10",
    )
    dfc.save_config(tmp_path, cfg)
    loaded = dfc.load_config(tmp_path)
    assert loaded.profiles == ["claude", "codex"]
    assert loaded.enforcement_chosen == ["local-hook"]
    assert loaded.enforcement_declined == ["ci"]


def test_save_config_overwrites_existing(tmp_path):
    dfc.save_config(tmp_path, dfc.DocsFirstConfig(profiles=["claude"]))
    dfc.save_config(tmp_path, dfc.DocsFirstConfig(profiles=["cursor"]))
    loaded = dfc.load_config(tmp_path)
    assert loaded.profiles == ["cursor"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_docs_first_config.py -k save -v`
Expected: FAIL with `AttributeError: module 'docs_first_config' has no attribute 'save_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/docs_first_config.py


def save_config(repo: Path, cfg: DocsFirstConfig) -> Path:
    """Write .docs-first/config.yml. Mutating — callers must have user consent."""

    path = Path(repo) / CONFIG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config(cfg), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_docs_first_config.py -v`
Expected: PASS (all prior + 3 new)

- [ ] **Step 5: Commit**

```bash
git add scripts/docs_first_config.py tests/test_docs_first_config.py
git commit -m "feat: add save_config write-on-consent primitive"
```

---

## Task 3: Document the agent-profile flow in SKILL.md + references

**Files:**
- Modify: `SKILL.md`
- Modify: `references/compliance-rules.md`

This task is documentation (no pytest). Verify by `grep` and by re-running the suite to confirm nothing regressed.

- [ ] **Step 1: Extend the AI-instruction bullet in SKILL.md**

In `SKILL.md`, replace this line (inside `## AI Instruction Files Alignment`):

```markdown
- Target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`.
```

with:

```markdown
- Base target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`.
- Plus each active agent profile's soft target (see `## Agent Profiles`): Cursor adds
  `.cursor/rules/docs-first.mdc`; Codex/generic use `AGENTS.md`.
```

- [ ] **Step 2: Add the `## Agent Profiles` section to SKILL.md**

Insert this new section immediately before `## Escalation Policy`:

```markdown
## Agent Profiles

The canonical method is single and agnostic; only *delivery* varies per AI agent.
A profile customizes where the always-on instruction lives and how the skill is
packaged — never the docs model or the method.

| Profile | Always-on soft target | Skill package dir |
|---|---|---|
| claude | `CLAUDE.md` | `.claude/skills/plan-docs-standardization/` |
| cursor | `.cursor/rules/docs-first.mdc` (frontmatter `alwaysApply: true`) | `.cursor/skills/plan-docs-standardization/` |
| codex | `AGENTS.md` | `.agents/skills/plan-docs-standardization/` |
| generic | `AGENTS.md` | (none) |

**Detect → ask → persist (first thing the skill does):**

1. Read `.docs-first/config.yml`. If it lists `profiles`, use them (authoritative).
2. Else detect by filesystem markers (`.claude/`, `.cursor/`, `.codex/`, `.agents/`).
3. Else ask the user which agent(s) they use. Never guess from model self-identification.
4. After resolving (and only with the user's consent), persist the decision:
   preview `render_config(...)` then write via `save_config(...)`. A read-only audit
   never writes this file. Record decisions, not observations (do not store "`.cursor/` exists").

**Multiple agents in one repo:** `profiles` is a list. When several are active, propose each
profile's soft target together; the docs tree and audit are shared.

**Soft-layer install offer:** soft targets are never auto-created (absent → INFO). When a profile
is active and its surface is absent, offer to install it with consent — for Cursor, generate the
rule with `python3 scripts/render_profile_artifacts.py cursor > .cursor/rules/docs-first.mdc`.
For Claude/Codex, append the canonical block to the user's existing `CLAUDE.md`/`AGENTS.md`.

**State file validation:** the audit reads `.docs-first/config.yml` when present and reports
`DOCS_FIRST_CONFIG_INVALID` (`WARN`) for unknown profile or enforcement-gate keys. Absent file
is never a finding.
```

- [ ] **Step 3: Document profiles + config in references/compliance-rules.md**

Append this block to the end of `references/compliance-rules.md`:

```markdown
## Agent Profiles & State

The method is agent-agnostic; delivery is per-profile (claude/cursor/codex/generic). Each
profile declares an always-on soft target (`CLAUDE.md` / `.cursor/rules/docs-first.mdc` /
`AGENTS.md`). Active profiles come from `.docs-first/config.yml` (`profiles:`) or, absent it,
filesystem markers. Active profiles' soft targets are audited structurally like the base
AI-instruction files.

`.docs-first/config.yml` records decisions (active profiles, chosen/declined enforcement gates),
not observations. It is written only on explicit user consent; a read-only audit never writes it.

### Config validity (WARN)

When `.docs-first/config.yml` is present, unknown profile keys or unknown enforcement-gate keys
are reported as `DOCS_FIRST_CONFIG_INVALID` (`WARN`). Absent file is never a finding.
```

- [ ] **Step 4: Verify the docs landed and the suite is green**

Run:

```bash
grep -q "## Agent Profiles" SKILL.md && echo "SKILL.md OK"
grep -q "DOCS_FIRST_CONFIG_INVALID" references/compliance-rules.md && echo "references OK"
python3 -m pytest tests/ -q
```

Expected: both "OK" lines print; the full suite passes (documentation changes do not affect tests).

- [ ] **Step 5: Commit**

```bash
git add SKILL.md references/compliance-rules.md
git commit -m "docs: document agent profiles, detect/ask/persist, and config validity"
```

---

## Self-Review

**Spec coverage (Plan 3 portion):**
- §5.3 lifecycle write-on-consent → Task 2 (`save_config`) + Task 3 (skill previews then writes; read-only never writes).
- §6 soft-layer delivery made visible → Task 1 (plan proposes per-active-profile diffs) + Task 3 (install offer).
- §3 / multi-profile → Task 3 ("Multiple agents in one repo").
- §8 runtime model → Task 3 table (skill package dirs per host).

**Deferred (correctly) to Plan 4:** all hard-layer gates (CI/branch protection, local hook, native Claude/Codex hooks), the gate consent flow, and §5.4 enforcement-drift reconciliation in the audit.

**Placeholder scan:** none — exact prose and code provided for every step.

**Type consistency:** `proposed_diffs(repo, ...)` already receives `repo`; the new local `ai_instruction_targets` set reuses `adm.ai_instruction_targets` (Plan 2) exactly; `save_config(repo, cfg)` reuses `DocsFirstConfig`, `CONFIG_REL`, `render_config` (Plan 1) exactly. Removing the dead `AI_INSTRUCTION_FILES` module constant has no other referent in the file (only the routing line used it).

---

## Next Plan (not in this file)
- **Plan 4 — Hard layer & enforcement:** CI workflow + branch-protection helper, local `core.hooksPath` hook, Claude/Codex native hooks, the never-force consent flow, and §5.4 enforcement-drift reconciliation (`ENFORCEMENT_GATE_MISSING` WARN / `NO_ENFORCEMENT_GATE` INFO) in the audit.
