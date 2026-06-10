# Agent Profiles — Foundation (Plan 1 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the agent-profile registry, environment detection, and the consent-aware `.docs-first/config.yml` state file that the rest of the per-agent feature depends on.

**Architecture:** Two new stdlib-only modules under `scripts/`. `agent_profiles.py` holds a frozen `AgentProfile` dataclass + a registry (claude/cursor/codex/generic) + filesystem detection. `docs_first_config.py` reads/writes the tiny fixed-schema state file (flat YAML subset, no PyYAML dependency, because the local git hook and CI must parse it with bare `python3`). A new read-only audit check validates the config when present. No content generation, soft layer, or gates yet — those are Plans 2–4.

**Tech Stack:** Python 3 (stdlib only), pytest. Tests import modules from `scripts/` via the existing `tests/conftest.py` path injection. Findings use the existing `audit_docs_model.Finding` / `make_finding` machinery.

**Spec:** `docs/superpowers/specs/2026-06-10-agent-profiles-and-enforcement-design.md` (§4.1 profile model, §5 detection & persistence).

**Scope note — schema choice:** The spec §5.2 shows a nested `enforcement:` block. This plan uses a **flat** schema (`enforcement_chosen`/`enforcement_declined`) so the zero-dependency parser stays trivial and unambiguous. It is still valid YAML; PyYAML would also read it. This is an intentional implementation-level deviation.

---

## File Structure

- **Create** `scripts/agent_profiles.py` — `AgentProfile` dataclass, `PROFILES` registry, `get_profile`, `detect_signal_profiles`, `resolve_active_profiles`.
- **Create** `scripts/docs_first_config.py` — `DocsFirstConfig` dataclass, `CONFIG_REL`, `render_config`, `load_config`.
- **Modify** `scripts/audit_docs_model.py` — add `check_agent_profiles_config` and call it from `audit_repository`.
- **Create** `tests/test_agent_profiles.py` — registry + detection + resolution tests.
- **Create** `tests/test_docs_first_config.py` — config render/parse round-trip tests.
- **Create** `tests/test_agent_profiles_audit.py` — audit validation tests.

---

## Task 1: AgentProfile dataclass + registry

**Files:**
- Create: `scripts/agent_profiles.py`
- Test: `tests/test_agent_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_profiles.py
import agent_profiles as ap


def test_registry_has_four_known_profiles():
    assert set(ap.PROFILES) == {"claude", "cursor", "codex", "generic"}


def test_claude_profile_fields():
    p = ap.get_profile("claude")
    assert p.soft_target == "CLAUDE.md"
    assert p.soft_wrapper is None
    assert p.skill_install == ".claude/skills/plan-docs-standardization/"
    assert p.native_hard_gate == "claude-hooks"


def test_cursor_profile_uses_mdc_wrapper_and_has_no_native_gate():
    p = ap.get_profile("cursor")
    assert p.soft_target == ".cursor/rules/docs-first.mdc"
    assert p.soft_wrapper == "mdc"
    assert p.skill_install == ".cursor/skills/plan-docs-standardization/"
    assert p.native_hard_gate is None


def test_codex_profile_uses_agents_md_and_agents_skills_path():
    p = ap.get_profile("codex")
    assert p.soft_target == "AGENTS.md"
    assert p.skill_install == ".agents/skills/plan-docs-standardization/"
    assert p.native_hard_gate == "codex-hooks"


def test_generic_profile_has_no_skill_or_gate():
    p = ap.get_profile("generic")
    assert p.soft_target == "AGENTS.md"
    assert p.skill_install is None
    assert p.native_hard_gate is None


def test_get_profile_unknown_raises():
    import pytest

    with pytest.raises(KeyError):
        ap.get_profile("windsurf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_profiles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_profiles'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/agent_profiles.py
#!/usr/bin/env python3
"""Declarative per-agent profiles: delivery adapters over the agnostic core."""

from __future__ import annotations

from dataclasses import dataclass, field


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_profiles.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_profiles.py tests/test_agent_profiles.py
git commit -m "feat: add agent-profile registry (claude/cursor/codex/generic)"
```

---

## Task 2: Filesystem detection of profiles

**Files:**
- Modify: `scripts/agent_profiles.py` (add `detect_signal_profiles`)
- Test: `tests/test_agent_profiles.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_agent_profiles.py


def test_detect_empty_repo_returns_no_profiles(tmp_path):
    assert ap.detect_signal_profiles(tmp_path) == []


def test_detect_cursor_and_claude_dirs(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    assert ap.detect_signal_profiles(tmp_path) == ["claude", "cursor"]


def test_detect_codex_via_either_marker(tmp_path):
    (tmp_path / ".agents").mkdir()
    assert ap.detect_signal_profiles(tmp_path) == ["codex"]


def test_detect_ignores_generic_which_has_no_signal(tmp_path):
    # generic has empty detect_dirs and must never be auto-detected
    (tmp_path / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    assert ap.detect_signal_profiles(tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_profiles.py -k detect -v`
Expected: FAIL with `AttributeError: module 'agent_profiles' has no attribute 'detect_signal_profiles'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/agent_profiles.py
from pathlib import Path  # add to the existing imports at the top of the file


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
```

> Note: move `from pathlib import Path` up beside `from dataclasses import ...` at the top; do not leave it mid-file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_profiles.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_profiles.py tests/test_agent_profiles.py
git commit -m "feat: detect active agent profiles from filesystem markers"
```

---

## Task 3: DocsFirstConfig dataclass + render (emit)

**Files:**
- Create: `scripts/docs_first_config.py`
- Test: `tests/test_docs_first_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_docs_first_config.py
import docs_first_config as dfc


def test_render_emits_flat_yaml_with_inline_lists():
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "cursor"],
        enforcement_chosen=["ci", "local-hook"],
        enforcement_declined=["claude-hooks"],
        updated="2026-06-10",
    )
    text = dfc.render_config(cfg)
    assert "version: 1" in text
    assert "profiles: [claude, cursor]" in text
    assert "enforcement_chosen: [ci, local-hook]" in text
    assert "enforcement_declined: [claude-hooks]" in text
    assert "updated: 2026-06-10" in text


def test_render_emits_empty_lists_as_brackets():
    cfg = dfc.DocsFirstConfig(profiles=[], enforcement_chosen=[], enforcement_declined=[])
    text = dfc.render_config(cfg)
    assert "profiles: []" in text
    assert "enforcement_chosen: []" in text


def test_config_rel_constant():
    assert dfc.CONFIG_REL == ".docs-first/config.yml"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_docs_first_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'docs_first_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/docs_first_config.py
#!/usr/bin/env python3
"""Read/write the .docs-first/config.yml state file.

Stdlib-only on purpose: the local git hook and CI must parse this with bare
python3, so we use a tiny flat-YAML subset (scalars + inline lists) rather than
depending on PyYAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CONFIG_REL = ".docs-first/config.yml"
SCHEMA_VERSION = 1


@dataclass
class DocsFirstConfig:
    profiles: list[str] = field(default_factory=list)
    enforcement_chosen: list[str] = field(default_factory=list)
    enforcement_declined: list[str] = field(default_factory=list)
    updated: str | None = None
    version: int = SCHEMA_VERSION


def _fmt_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def render_config(cfg: DocsFirstConfig) -> str:
    lines = [
        "# Managed by plan-docs-standardization. Records decisions, not observations.",
        f"version: {cfg.version}",
        f"profiles: {_fmt_list(cfg.profiles)}",
        f"enforcement_chosen: {_fmt_list(cfg.enforcement_chosen)}",
        f"enforcement_declined: {_fmt_list(cfg.enforcement_declined)}",
    ]
    if cfg.updated is not None:
        lines.append(f"updated: {cfg.updated}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_docs_first_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/docs_first_config.py tests/test_docs_first_config.py
git commit -m "feat: model and render .docs-first/config.yml state file"
```

---

## Task 4: Parse + load config (round-trip)

**Files:**
- Modify: `scripts/docs_first_config.py` (add `parse_config`, `load_config`)
- Test: `tests/test_docs_first_config.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_docs_first_config.py
from pathlib import Path


def test_parse_round_trip():
    cfg = dfc.DocsFirstConfig(
        profiles=["claude", "cursor"],
        enforcement_chosen=["ci"],
        enforcement_declined=[],
        updated="2026-06-10",
    )
    parsed = dfc.parse_config(dfc.render_config(cfg))
    assert parsed.profiles == ["claude", "cursor"]
    assert parsed.enforcement_chosen == ["ci"]
    assert parsed.enforcement_declined == []
    assert parsed.updated == "2026-06-10"
    assert parsed.version == 1


def test_parse_handles_empty_lists_and_comments():
    text = "# comment\nversion: 1\nprofiles: []\nenforcement_chosen: []\nenforcement_declined: []\n"
    parsed = dfc.parse_config(text)
    assert parsed.profiles == []
    assert parsed.enforcement_chosen == []


def test_load_config_missing_returns_none(tmp_path):
    assert dfc.load_config(tmp_path) is None


def test_load_config_reads_file(tmp_path):
    target = tmp_path / dfc.CONFIG_REL
    target.parent.mkdir(parents=True)
    target.write_text(
        dfc.render_config(dfc.DocsFirstConfig(profiles=["codex"])), encoding="utf-8"
    )
    parsed = dfc.load_config(tmp_path)
    assert parsed is not None
    assert parsed.profiles == ["codex"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_docs_first_config.py -k "parse or load" -v`
Expected: FAIL with `AttributeError: module 'docs_first_config' has no attribute 'parse_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/docs_first_config.py


def _parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    if raw.isdigit():
        return int(raw)
    return raw.strip("\"'")


def parse_config(text: str) -> DocsFirstConfig:
    data: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        data[key.strip()] = _parse_value(value)

    return DocsFirstConfig(
        profiles=list(data.get("profiles", []) or []),
        enforcement_chosen=list(data.get("enforcement_chosen", []) or []),
        enforcement_declined=list(data.get("enforcement_declined", []) or []),
        updated=(data.get("updated") or None),
        version=int(data.get("version", SCHEMA_VERSION)),
    )


def load_config(repo: Path) -> DocsFirstConfig | None:
    path = Path(repo) / CONFIG_REL
    if not path.exists():
        return None
    return parse_config(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_docs_first_config.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/docs_first_config.py tests/test_docs_first_config.py
git commit -m "feat: parse and load .docs-first/config.yml (stdlib round-trip)"
```

---

## Task 5: Resolve active profiles (detection hierarchy)

**Files:**
- Modify: `scripts/agent_profiles.py` (add `resolve_active_profiles`)
- Test: `tests/test_agent_profiles.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_agent_profiles.py
import docs_first_config as dfc


def _write_cfg(repo, profiles):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(profiles=profiles)), encoding="utf-8")


def test_resolve_prefers_config(tmp_path):
    _write_cfg(tmp_path, ["codex"])
    (tmp_path / ".cursor").mkdir()  # signal disagrees; config wins
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == ["codex"]
    assert source == "config"


def test_resolve_falls_back_to_signals(tmp_path):
    (tmp_path / ".cursor").mkdir()
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == ["cursor"]
    assert source == "signals"


def test_resolve_undetermined_when_nothing(tmp_path):
    profiles, source = ap.resolve_active_profiles(tmp_path)
    assert profiles == []
    assert source == "undetermined"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_profiles.py -k resolve -v`
Expected: FAIL with `AttributeError: module 'agent_profiles' has no attribute 'resolve_active_profiles'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to scripts/agent_profiles.py
import docs_first_config as dfc  # add near the top imports


def resolve_active_profiles(repo: Path) -> tuple[list[str], str]:
    """Return (profile_keys, source) following the detection hierarchy:

    1. persisted config  -> source "config"
    2. filesystem signals -> source "signals"
    3. neither            -> ([], "undetermined")  (the skill then asks the user)
    """

    repo = Path(repo)
    config = dfc.load_config(repo)
    if config is not None and config.profiles:
        return list(config.profiles), "config"

    detected = detect_signal_profiles(repo)
    if detected:
        return detected, "signals"

    return [], "undetermined"
```

> Note: `agent_profiles` and `docs_first_config` are sibling modules in `scripts/`; the cross-import works because `tests/conftest.py` puts `scripts/` on `sys.path` (and the audit script does the same at runtime via its own `sys.path` insertion — confirmed in Task 6).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_profiles.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_profiles.py tests/test_agent_profiles.py
git commit -m "feat: resolve active profiles via config -> signals -> undetermined"
```

---

## Task 6: Audit check — validate config when present

**Files:**
- Modify: `scripts/audit_docs_model.py` (add `check_agent_profiles_config`, call it in `audit_repository`)
- Test: `tests/test_agent_profiles_audit.py`

Context: `audit_docs_model.py` already inserts its own dir on `sys.path` at import time (lines near the top of the file: `SCRIPT_DIR = Path(__file__)... sys.path.insert(...)` pattern used by the sibling scripts). Confirm `agent_profiles`/`docs_first_config` import cleanly from within it. The known enforcement-gate keys for this plan are `ci`, `local-hook`, `claude-hooks`, `codex-hooks`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_profiles_audit.py
import audit_docs_model as adm
import docs_first_config as dfc


def _codes(findings):
    return {f.code for f in findings}


def _write_cfg(repo, **kwargs):
    target = repo / dfc.CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dfc.render_config(dfc.DocsFirstConfig(**kwargs)), encoding="utf-8")


def test_no_config_no_finding(tmp_path):
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert findings == []


def test_valid_config_no_finding(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["ci"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert findings == []


def test_unknown_profile_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["windsurf"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert _codes(findings) == {"DOCS_FIRST_CONFIG_INVALID"}
    assert findings[0].severity == "WARN"


def test_unknown_gate_warns(tmp_path):
    _write_cfg(tmp_path, profiles=["claude"], enforcement_chosen=["telepathy"])
    findings = []
    adm.check_agent_profiles_config(tmp_path, findings)
    assert _codes(findings) == {"DOCS_FIRST_CONFIG_INVALID"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_profiles_audit.py -v`
Expected: FAIL with `AttributeError: module 'audit_docs_model' has no attribute 'check_agent_profiles_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# add near the other check_* functions in scripts/audit_docs_model.py
import agent_profiles as _ap  # add beside the existing top-of-file imports
import docs_first_config as _dfc

KNOWN_ENFORCEMENT_GATES = {"ci", "local-hook", "claude-hooks", "codex-hooks"}


def check_agent_profiles_config(repo: Path, findings: list[Finding]) -> None:
    """Validate .docs-first/config.yml when present. Absent file is not a finding
    (detection/asking is skill behavior, not the audit's job)."""

    config = _dfc.load_config(repo)
    if config is None:
        return

    unknown_profiles = [p for p in config.profiles if p not in _ap.PROFILES]
    unknown_gates = [
        g
        for g in (config.enforcement_chosen + config.enforcement_declined)
        if g not in KNOWN_ENFORCEMENT_GATES
    ]
    if unknown_profiles or unknown_gates:
        details = []
        if unknown_profiles:
            details.append(f"unknown profiles {sorted(set(unknown_profiles))}")
        if unknown_gates:
            details.append(f"unknown enforcement gates {sorted(set(unknown_gates))}")
        make_finding(
            findings,
            "WARN",
            "DOCS_FIRST_CONFIG_INVALID",
            _dfc.CONFIG_REL,
            f".docs-first/config.yml has {'; '.join(details)}.",
        )
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python3 -m pytest tests/test_agent_profiles_audit.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire into `audit_repository`**

In `scripts/audit_docs_model.py`, inside `audit_repository`, add the call alongside the other `check_*` calls (right after `check_ai_instruction_files(repo, findings)`):

```python
    check_ai_instruction_files(repo, findings)
    check_agent_profiles_config(repo, findings)
```

- [ ] **Step 6: Run the full suite to verify no regression**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — the prior 51 tests plus the new Plan-1 tests, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_agent_profiles_audit.py
git commit -m "feat: audit-validate .docs-first/config.yml profile/gate keys (WARN)"
```

---

## Self-Review

**Spec coverage (Plan 1 portion):**
- §4.1 profile model (soft_target/skill_install/native_hard_gate/detect signals) → Task 1.
- §5.1 detection hierarchy (config → signals → ask) → Tasks 2, 5 (the "ask" is left to the skill; the script returns `undetermined`).
- §5.2 state file storing decisions, flat schema → Tasks 3, 4.
- §5.3 lifecycle read/create/update → `load_config`/`render_config` provide read+emit; create/update-on-consent is wired by the skill in a later plan (Plan 2 install path). Writing is never done by the audit (read-only preserved) — Task 6 only reads.
- §5.4 enforcement-drift reconciliation → **deferred to Plan 3** (needs the gates to exist). Task 6 covers config *validity* only; full intent-vs-reality reconciliation is Plan 3.

**Out-of-scope for Plan 1 (correctly deferred):** soft-layer generation, gate generation/install, generator + anti-drift, the skill's ask/persist UX. These are Plans 2–4.

**Placeholder scan:** none — every code/test step is complete.

**Type consistency:** `AgentProfile` fields used identically across Tasks 1/2/5/6; `DocsFirstConfig` fields (`profiles`, `enforcement_chosen`, `enforcement_declined`, `updated`, `version`) consistent across Tasks 3/4/5/6; `CONFIG_REL`, `KNOWN_ENFORCEMENT_GATES`, `check_agent_profiles_config` names stable.

---

## Next Plans (not in this file)
- **Plan 2 — Soft layer & install path:** per-agent always-on instruction generation (CLAUDE.md / `.cursor/rules/*.mdc` / `AGENTS.md`), skill-package install per host, the skill's detect→ask→persist UX, multi-profile composition.
- **Plan 3 — Hard layer & enforcement:** CI workflow + branch-protection helper, local `core.hooksPath` hook, Claude/Codex native hooks, the consent flow, and §5.4 enforcement-drift reconciliation in the audit.
- **Plan 4 — Generator & anti-drift:** `scripts/render_profile_artifacts.py` composing `overlay ⊕ canonical`, committed-output tests that fail CI on drift.
