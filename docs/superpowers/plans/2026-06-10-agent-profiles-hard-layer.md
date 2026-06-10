# Agent Profiles — Hard Layer & Enforcement (Plan 4 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the deterministic enforcement-gate artifacts (CI, local pre-commit, native Claude/Codex hooks), detect their presence, reconcile chosen-vs-present in the audit, and document the never-force consent flow.

**Architecture:** A new module `scripts/enforcement_gates.py` renders each gate artifact from a single `audit_cmd` and detects gate presence on disk. The audit gains `check_enforcement_gates`, comparing `.docs-first/config.yml` intent (`enforcement_chosen`) against filesystem reality: chosen-but-missing → `ENFORCEMENT_GATE_MISSING` (WARN); nothing chosen and nothing present (in a docs repo) → `NO_ENFORCEMENT_GATE` (INFO, never BLOCKER). SKILL.md documents the consent flow (never force; warn with concrete risks; ask with a recommendation; install with preview) and the gh-api branch-protection step.

**Tech Stack:** Python 3 (stdlib only), pytest. Builds on Plan 1 (`docs_first_config`, `KNOWN_ENFORCEMENT_GATES` in `audit_docs_model`).

**Spec:** `docs/superpowers/specs/2026-06-10-agent-profiles-and-enforcement-design.md` (§7 hard layer + consent model, §5.4 enforcement-drift reconciliation).

**Cycle-avoidance note:** `enforcement_gates.py` must NOT import `audit_docs_model` (the audit imports it). It keeps its own gate→path mapping. The audit iterates its existing `KNOWN_ENFORCEMENT_GATES` and calls `_eg.gate_present`.

**Native-hook caveat:** the generated Claude/Codex hook configs follow the documented schemas but should be verified against the installed tool version (Codex hooks path/format changed recently). Tests assert structure (valid JSON + key fields), not live-tool behavior.

---

## File Structure

- **Create** `scripts/enforcement_gates.py` — `DEFAULT_AUDIT_CMD`, `render_ci_workflow`, `render_precommit_hook`, `render_claude_hooks`, `render_codex_hooks`, `GATE_PATHS`, `gate_present`.
- **Modify** `scripts/audit_docs_model.py` — add `check_enforcement_gates`; call it in `audit_repository`.
- **Modify** `SKILL.md` — add `## Enforcement Gates` section.
- **Modify** `references/compliance-rules.md` — document the two reconciliation codes.
- **Create** `tests/test_enforcement_gates.py` — render + presence tests.
- **Create** `tests/test_enforcement_audit.py` — reconciliation tests.

---

## Task 1: Render CI workflow + local pre-commit hook

**Files:**
- Create: `scripts/enforcement_gates.py`
- Test: `tests/test_enforcement_gates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enforcement_gates.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enforcement_gates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'enforcement_gates'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/enforcement_gates.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_enforcement_gates.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/enforcement_gates.py tests/test_enforcement_gates.py
git commit -m "feat: render CI workflow and local pre-commit gate artifacts"
```

---

## Task 2: Render native Claude + Codex hook configs

**Files:**
- Modify: `scripts/enforcement_gates.py`
- Test: `tests/test_enforcement_gates.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_enforcement_gates.py
import json


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enforcement_gates.py -k hooks -v`
Expected: FAIL with `AttributeError: module 'enforcement_gates' has no attribute 'render_claude_hooks'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/enforcement_gates.py


def render_claude_hooks(audit_cmd: str = DEFAULT_AUDIT_CMD) -> str:
    """Claude Code settings.json hooks block: run the audit at Stop; exit 2 blocks."""

    data = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": audit_cmd}]}
            ]
        }
    }
    return json.dumps(data, indent=2) + "\n"


def render_codex_hooks(audit_cmd: str = DEFAULT_AUDIT_CMD) -> str:
    """Codex .codex/hooks.json: PreToolUse on patch/commit; exit 2 (deny) blocks."""

    data = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "^apply_patch$",
                    "hooks": [{"type": "command", "command": audit_cmd}],
                }
            ]
        }
    }
    return json.dumps(data, indent=2) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_enforcement_gates.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/enforcement_gates.py tests/test_enforcement_gates.py
git commit -m "feat: render native Claude and Codex hook gate configs"
```

---

## Task 3: Detect gate presence on disk

**Files:**
- Modify: `scripts/enforcement_gates.py` (add `GATE_PATHS`, `gate_present`)
- Test: `tests/test_enforcement_gates.py` (append)

Presence is a pragmatic proxy (file existence, plus a `"hooks"` marker for the Claude settings file). It is intentionally coarse — it answers "did the user install this gate?", not "is it perfectly configured?".

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_enforcement_gates.py


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enforcement_gates.py -k gate_present -v`
Expected: FAIL with `AttributeError: module 'enforcement_gates' has no attribute 'gate_present'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/enforcement_gates.py

GATE_PATHS = {
    "ci": ".github/workflows/docs-audit.yml",
    "local-hook": ".githooks/pre-commit",
    "claude-hooks": ".claude/settings.json",
    "codex-hooks": ".codex/hooks.json",
}


def gate_present(repo: Path, gate: str) -> bool:
    rel = GATE_PATHS.get(gate)
    if rel is None:
        return False
    path = Path(repo) / rel
    if not path.exists():
        return False
    if gate == "claude-hooks":
        # settings.json exists for many reasons; require a hooks marker.
        return '"hooks"' in path.read_text(encoding="utf-8")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_enforcement_gates.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/enforcement_gates.py tests/test_enforcement_gates.py
git commit -m "feat: detect enforcement-gate presence on disk"
```

---

## Task 4: Audit reconciliation — intent vs reality

**Files:**
- Modify: `scripts/audit_docs_model.py` (add `check_enforcement_gates`; wire into `audit_repository`)
- Test: `tests/test_enforcement_audit.py`

Context: `_dfc` (docs_first_config), `_ap`, and `KNOWN_ENFORCEMENT_GATES` already exist in `audit_docs_model.py` from Plan 1. Add `import enforcement_gates as _eg` near the others. `NO_ENFORCEMENT_GATE` (INFO) only fires in a docs repo (`discover_mode == "alignment"`) so empty/non-docs dirs stay quiet.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enforcement_audit.py
import audit_docs_model as adm
import docs_first_config as dfc


def _codes(findings):
    return {f.code for f in findings}


def _write_cfg(repo, **kwargs):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(**kwargs)), encoding="utf-8")


def test_chosen_gate_missing_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert "ENFORCEMENT_GATE_MISSING" in _codes(findings)
    assert all(f.severity != "BLOCKER" for f in findings)


def test_chosen_gate_present_no_warn(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    wf = tmp_path / ".github" / "workflows" / "docs-audit.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: x\n", encoding="utf-8")
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert "ENFORCEMENT_GATE_MISSING" not in _codes(findings)


def test_no_gate_in_docs_repo_infos(tmp_path):
    (tmp_path / "docs").mkdir()  # alignment mode
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert _codes(findings) == {"NO_ENFORCEMENT_GATE"}
    assert findings[0].severity == "INFO"


def test_no_gate_in_non_docs_repo_is_quiet(tmp_path):
    findings = []
    adm.check_enforcement_gates(tmp_path, findings)
    assert findings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enforcement_audit.py -v`
Expected: FAIL with `AttributeError: module 'audit_docs_model' has no attribute 'check_enforcement_gates'`

- [ ] **Step 3: Write minimal implementation**

Add the import near the other local imports at the top of `scripts/audit_docs_model.py`:

```python
import enforcement_gates as _eg
```

Add the function (next to `check_agent_profiles_config`):

```python
def check_enforcement_gates(repo: Path, findings: list[Finding]) -> None:
    """Reconcile chosen enforcement gates (.docs-first/config.yml) with what is on disk.

    Chosen-but-missing -> WARN. Nothing chosen and nothing present (docs repo only)
    -> INFO. Never a BLOCKER — the skill never forces a gate.
    """

    config = _dfc.load_config(repo)
    chosen = set(config.enforcement_chosen) if config else set()
    present = {g for g in KNOWN_ENFORCEMENT_GATES if _eg.gate_present(repo, g)}

    for gate in sorted(chosen - present):
        make_finding(
            findings,
            "WARN",
            "ENFORCEMENT_GATE_MISSING",
            _eg.GATE_PATHS.get(gate, gate),
            f"Enforcement gate '{gate}' is chosen in .docs-first/config.yml but not "
            "installed. Re-install it or remove it from the config.",
        )

    if not chosen and not present and discover_mode(repo) == "alignment":
        make_finding(
            findings,
            "INFO",
            "NO_ENFORCEMENT_GATE",
            ".docs-first/config.yml",
            "No enforcement gate active. The Docs-First model is advisory only; "
            "code can drift from docs. Consider a CI/branch-protection or pre-commit gate.",
        )
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python3 -m pytest tests/test_enforcement_audit.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire into `audit_repository`**

In `scripts/audit_docs_model.py`, add the call right after `check_agent_profiles_config(repo, findings)`:

```python
    check_agent_profiles_config(repo, findings)
    check_enforcement_gates(repo, findings)
```

- [ ] **Step 6: Run the full suite (no regression)**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — all prior tests plus the new ones, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_enforcement_audit.py
git commit -m "feat: reconcile enforcement-gate intent vs reality in audit"
```

---

## Task 5: Document the enforcement consent flow

**Files:**
- Modify: `SKILL.md`
- Modify: `references/compliance-rules.md`

Documentation task (no pytest). Verify with `grep` and re-run the suite.

- [ ] **Step 1: Add the `## Enforcement Gates` section to SKILL.md**

Insert immediately before `## Escalation Policy`:

```markdown
## Enforcement Gates

Instructions are *soft* (they shape the agent but it can drift). True enforcement is a
*deterministic gate* that runs the audit outside the model. Gates are **never forced**.

Gate options (all run the docs audit; `audit_cmd` points at the installed audit script):

| Gate key | Artifact | Strength | Scope |
|---|---|---|---|
| `ci` | `.github/workflows/docs-audit.yml` + branch protection | unbypassable (real gate) | team-wide |
| `local-hook` | `.githooks/pre-commit` (+ `git config core.hooksPath .githooks`) | bypassable (`--no-verify`) | per dev |
| `claude-hooks` | `.claude/settings.json` Stop hook | in-session (Claude only) | per dev |
| `codex-hooks` | `.codex/hooks.json` PreToolUse deny | in-session (Codex only) | per repo |

**Consent flow (never force):**

1. **Never obligate** a gate.
2. **Warn, concretely:** no gate → docs drift silently and eventually lie; soft-only → fails
   under pressure (big PR, deadline); local-hook only → bypassable, and teammates without it commit
   non-compliant code.
3. **Ask which to adopt, leading with a recommendation:** CI + branch protection, plus the local
   hook; add native hooks where the agent offers them.
4. **Instruct + offer to install, with a preview** of every file write / config change / `gh api`
   call before acting. Generate artifacts with `enforcement_gates.render_*`. Branch protection is a
   repo setting, not a file: `gh api -X PUT repos/{owner}/{repo}/branches/main/protection ...`
   (needs admin); degrade gracefully (generate the workflow, instruct the manual toggle) when the
   token lacks rights.

**Persisted choices:** record accepted gates in `.docs-first/config.yml` `enforcement_chosen` and
refusals in `enforcement_declined` (never re-ask). The audit then reconciles intent vs reality
(see below). Native hook configs follow documented schemas — verify against the installed tool.
```

- [ ] **Step 2: Document the reconciliation codes in references/compliance-rules.md**

Append to `references/compliance-rules.md`:

```markdown
### Enforcement reconciliation

The audit compares `.docs-first/config.yml` `enforcement_chosen` against installed gate artifacts
(`.github/workflows/docs-audit.yml`, `.githooks/pre-commit`, `.claude/settings.json` with a `hooks`
key, `.codex/hooks.json`):

- A chosen gate with no artifact on disk => `ENFORCEMENT_GATE_MISSING` (`WARN`).
- No gate chosen and none present, in a docs repo (alignment mode) => `NO_ENFORCEMENT_GATE` (`INFO`).

Enforcement is never a `BLOCKER`: the skill never forces a gate.
```

- [ ] **Step 3: Verify the docs landed and the suite is green**

Run:

```bash
grep -q "## Enforcement Gates" SKILL.md && echo "SKILL.md OK"
grep -q "ENFORCEMENT_GATE_MISSING" references/compliance-rules.md && echo "references OK"
python3 -m pytest tests/ -q
```

Expected: both "OK" lines print; the full suite passes.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references/compliance-rules.md
git commit -m "docs: document enforcement gates and never-force consent flow"
```

---

## Self-Review

**Spec coverage (Plan 4 portion):**
- §7.1 three gate locations → Tasks 1–2 (CI, local hook, native Claude/Codex hooks).
- §7.2 consent model (never force; warn; ask with recommendation; install with preview; branch protection via gh api) → Task 5.
- §5.4 enforcement-drift reconciliation (`ENFORCEMENT_GATE_MISSING` WARN / `NO_ENFORCEMENT_GATE` INFO, never BLOCKER) → Tasks 3–4.

**Placeholder scan:** none — exact code and prose for every step.

**Type consistency:** `render_ci_workflow`/`render_precommit_hook`/`render_claude_hooks`/`render_codex_hooks`/`GATE_PATHS`/`gate_present` consistent across Tasks 1–4; `check_enforcement_gates` reuses Plan-1 `KNOWN_ENFORCEMENT_GATES`, `_dfc.load_config`, `discover_mode`, `make_finding` exactly; gate keys (`ci`/`local-hook`/`claude-hooks`/`codex-hooks`) match `KNOWN_ENFORCEMENT_GATES` from Plan 1 and `GATE_PATHS` here.

**Cycle check:** `enforcement_gates.py` imports only stdlib; `audit_docs_model.py` imports it — no cycle.

---

## Feature complete after this plan
Plans 1–4 together deliver: agnostic core + per-agent profiles, detection & `.docs-first/config.yml` persistence, single-source soft-layer generation with anti-drift, plan/install integration with consent, and the optional hard-layer gates with reconciliation. Recommended follow-up: a holistic `requesting-code-review` pass over the whole branch, then `finishing-a-development-branch`.
