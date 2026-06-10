# Self-Describing Docs Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canonical docs model self-describing — a durable ownership map in `docs/index.md`, a behavioral map directive + pointer in the AI-instruction guidelines block, and an optional living `docs/reports/CURRENT_STATE.md` handoff snapshot — with lenient enforcement (bootstrap emits it; alignment WARN/INFO, never BLOCKER).

**Architecture:** Two new read-only audit checks in `scripts/audit_docs_model.py` (`check_index_map` → `INDEX_MAP_MISSING` WARN; an AI-instruction `docs/index.md` pointer check → `AI_INSTRUCTION_MAP_POINTER_MISSING` INFO), corresponding diff routing in `scripts/build_docs_alignment_plan.py`, enriched bundled templates, and updated reference/spec docs. Detection is by link target (language-agnostic). No existing passing project becomes a BLOCKER.

**Tech Stack:** Python 3.12, pytest. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-06-10-self-describing-docs-model-design.md`

**Run tests from the repo root.** `tests/conftest.py` puts `scripts/` on `sys.path`, so `import audit_docs_model as adm` works.

---

### Task 1: `check_index_map` audit check (`INDEX_MAP_MISSING`, WARN)

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_index_map.py` (create)

Detection: `docs/index.md` must contain markdown links resolving to a **strict majority** of the navigable canonical docs (the required set minus `index.md`, `requirements-mkdocs.txt`, `mkdocs.yml`). Reuses `iter_markdown_links` / `resolve_link_target`. Absent `index.md` produces no finding here (handled by the required-files check).

- [ ] **Step 1: Write the failing test**

Create `tests/test_index_map.py`:

```python
from pathlib import Path

import audit_docs_model as adm

NAV = [
    "docs/PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/GLOSSARY.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/nfr/NON_FUNCTIONAL.md",
    "docs/features/INDEX.md",
    "docs/reports/README.md",
]


def _write_index(repo: Path, body: str) -> None:
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.md").write_text(body, encoding="utf-8")


def _codes(findings):
    return {f.code for f in findings}


def test_index_map_missing_when_no_links(tmp_path):
    _write_index(tmp_path, "# Docs\n\nNothing here.\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert _codes(findings) == {"INDEX_MAP_MISSING"}
    assert findings[0].severity == "WARN"


def test_index_map_present_when_majority_linked(tmp_path):
    links = "\n".join(f"- [doc]({rel[len('docs/'):]})" for rel in NAV)
    _write_index(tmp_path, "# Docs\n\n" + links + "\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_index_map_warns_below_strict_majority(tmp_path):
    # 4 of 9 navigable docs linked -> not a strict majority -> WARN
    links = "\n".join(f"- [doc]({rel[len('docs/'):]})" for rel in NAV[:4])
    _write_index(tmp_path, "# Docs\n\n" + links + "\n")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert _codes(findings) == {"INDEX_MAP_MISSING"}


def test_index_map_no_finding_when_index_absent(tmp_path):
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_index_map.py -v`
Expected: FAIL with `AttributeError: module 'audit_docs_model' has no attribute 'check_index_map'`

- [ ] **Step 3: Add the constant and function**

In `scripts/audit_docs_model.py`, after the `REQUIRED_FILES`/`FEATURE_REQUIRED_FILES` block (around line 37), add the navigable set:

```python
INDEX_MAP_NAVIGABLE = [
    "docs/PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/GLOSSARY.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/nfr/NON_FUNCTIONAL.md",
    "docs/features/INDEX.md",
    "docs/reports/README.md",
]
```

Then add the check function. Place it immediately after `check_markdown_links` (after line 551) so the link helpers are already defined above it:

```python
def check_index_map(repo: Path, findings: list[Finding]) -> None:
    """WARN when docs/index.md is not a navigational map.

    A map links to a strict majority of the navigable canonical docs. Detection is
    by resolved link target, independent of language. Absent index.md is handled by
    the required-files check, not here.
    """

    index_path = repo / "docs" / "index.md"
    if not index_path.exists():
        return

    navigable = {(repo / rel).resolve() for rel in INDEX_MAP_NAVIGABLE}
    linked: set[Path] = set()
    for _line_number, target in iter_markdown_links(index_path):
        resolved = resolve_link_target(repo, index_path, target)
        if resolved is not None:
            linked.add(resolved.resolve())

    hits = len(navigable & linked)
    if hits * 2 <= len(INDEX_MAP_NAVIGABLE):  # not a strict majority
        make_finding(
            findings,
            "WARN",
            "INDEX_MAP_MISSING",
            "docs/index.md",
            "docs/index.md lacks a documentation map: it links to "
            f"{hits} of {len(INDEX_MAP_NAVIGABLE)} canonical docs. A navigational map "
            "should link to a majority of them.",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_index_map.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_index_map.py
git commit -m "feat: detect missing documentation map in docs/index.md (WARN)"
```

---

### Task 2: AI-instruction `docs/index.md` pointer check (`AI_INSTRUCTION_MAP_POINTER_MISSING`, INFO)

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_index_map.py` (add cases), `tests/test_ai_instruction_audit.py` (update two existing tests)

Adds a `references_doc_index` helper and, inside `check_ai_instruction_files`, an INFO finding when an **existing** AI-instruction file has no markdown link resolving to `docs/index.md`. `detect_ai_instruction_shapes` is unchanged, so no file that passes today becomes a BLOCKER.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_map.py`:

```python
def test_ai_file_without_pointer_gets_info(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Project\n\nNo pointer here.\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    info = {f.code for f in findings if f.severity == "INFO" and f.path == "CLAUDE.md"}
    assert "AI_INSTRUCTION_MAP_POINTER_MISSING" in info


def test_ai_file_with_pointer_has_no_pointer_finding(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\nSee [the map](docs/index.md).\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {f.code for f in findings if f.path == "CLAUDE.md"}
    assert "AI_INSTRUCTION_MAP_POINTER_MISSING" not in codes


def test_pointer_missing_is_never_blocker(tmp_path):
    # workflow + principles present (no BLOCKER), but no docs/index.md pointer
    sections = adm.load_canonical_sections()
    text = "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)
    (tmp_path / "CLAUDE.md").write_text(text + "\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = {f.code for f in findings if f.severity == "BLOCKER" and f.path == "CLAUDE.md"}
    assert blockers == set()
    info = {f.code for f in findings if f.severity == "INFO" and f.path == "CLAUDE.md"}
    assert info == {"AI_INSTRUCTION_MAP_POINTER_MISSING"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_index_map.py::test_ai_file_without_pointer_gets_info -v`
Expected: FAIL (`AI_INSTRUCTION_MAP_POINTER_MISSING` not present; helper not defined)

- [ ] **Step 3: Add the helper and extend the check**

In `scripts/audit_docs_model.py`, add the helper just above `check_ai_instruction_files` (around line 671):

```python
def references_doc_index(path: Path, repo: Path) -> bool:
    """True when the markdown file links to docs/index.md (by resolved target)."""

    index_resolved = (repo / "docs" / "index.md").resolve()
    for _line_number, target in iter_markdown_links(path):
        resolved = resolve_link_target(repo, path, target)
        if resolved is not None and resolved.resolve() == index_resolved:
            return True
    return False
```

Then, inside `check_ai_instruction_files`, after the `if not has_principles:` block and before the loop continues (i.e., as the last thing done for an existing file, around line 706), add:

```python
        if not references_doc_index(path, repo):
            make_finding(
                findings,
                "INFO",
                "AI_INSTRUCTION_MAP_POINTER_MISSING",
                rel,
                "AI instruction file does not reference docs/index.md (the documentation "
                "map). Add a pointer so agents consult the map before writing docs.",
            )
```

- [ ] **Step 4: Update the two existing tests that now also see the INFO finding**

In `tests/test_ai_instruction_audit.py`:

Replace `test_identical_file_produces_no_finding` so the canonical fixture also carries the pointer (a fully canonical file produces no finding):

```python
def test_identical_file_produces_no_finding(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\nSee [docs/index.md](docs/index.md).\n\n" + _canonical_text() + "\n",
        encoding="utf-8",
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert _codes_for(findings, "CLAUDE.md") == set()
```

Replace `test_copilot_nested_path_detected` to expect the pointer INFO alongside the section BLOCKER:

```python
def test_copilot_nested_path_detected(tmp_path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "copilot-instructions.md").write_text("# x\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = _codes_for(findings, ".github/copilot-instructions.md")
    assert codes == {"AI_INSTRUCTION_SECTION_MISSING", "AI_INSTRUCTION_MAP_POINTER_MISSING"}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_index_map.py tests/test_ai_instruction_audit.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_index_map.py tests/test_ai_instruction_audit.py
git commit -m "feat: flag AI-instruction files missing a docs/index.md pointer (INFO)"
```

---

### Task 3: Wire checks into `audit_repository`; confirm `CURRENT_STATE.md` is never a finding

**Files:**
- Modify: `scripts/audit_docs_model.py:733-754` (`audit_repository`)
- Test: `tests/test_index_map.py` (add cases)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_map.py`:

```python
def test_audit_repository_runs_index_map_check(tmp_path):
    # Minimal repo with a docs/index.md that has no map -> result includes the WARN code.
    _write_index(tmp_path, "# Docs\n\nno map\n")
    result = adm.audit_repository(tmp_path)
    codes = {f["code"] for f in result["findings"]}
    assert "INDEX_MAP_MISSING" in codes


def test_current_state_absence_is_never_a_finding(tmp_path):
    # A repo without docs/reports/CURRENT_STATE.md must not produce any finding for it.
    _write_index(tmp_path, "# Docs\n\nno map\n")
    result = adm.audit_repository(tmp_path)
    paths = {f["path"] for f in result["findings"]}
    assert "docs/reports/CURRENT_STATE.md" not in paths
    codes = {f["code"] for f in result["findings"]}
    assert not any("CURRENT_STATE" in code for code in codes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_index_map.py::test_audit_repository_runs_index_map_check -v`
Expected: FAIL (`INDEX_MAP_MISSING` not in `result["findings"]` because the check isn't wired in)

- [ ] **Step 3: Wire `check_index_map` into `audit_repository`**

In `scripts/audit_docs_model.py`, inside `audit_repository`, add the call right after `check_mkdocs_nav(repo, findings)` (line 753) and before `check_ai_instruction_files`:

```python
    check_mkdocs_nav(repo, findings)
    check_index_map(repo, findings)
    check_ai_instruction_files(repo, findings)
```

(No code is needed for `CURRENT_STATE.md`: it is not in `REQUIRED_FILES` and no check references it, so its absence is silent by construction. The second test pins that.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_index_map.py -v`
Expected: PASS (all)

- [ ] **Step 5: Run the full suite to catch regressions**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all; the two updated AI-instruction tests pass)

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_index_map.py
git commit -m "feat: wire documentation-map check into audit_repository"
```

---

### Task 4: Enrich bundled templates + `load_canonical_map_section` helper

**Files:**
- Modify: `assets/templates/docs/index.md`
- Modify: `assets/templates/ai-instructions/guidelines.en.md`
- Create: `assets/templates/docs/reports/CURRENT_STATE.md`
- Modify: `assets/templates/docs/reports/README.md`
- Modify: `assets/templates/docs/ROADMAP.md`, `assets/templates/docs/BACKLOG.md`
- Modify: `scripts/audit_docs_model.py` (add `AI_INSTRUCTION_MAP_HEADING`, `load_canonical_map_section`)
- Test: `tests/test_templates_map.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_templates_map.py`:

```python
from pathlib import Path

import audit_docs_model as adm

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "assets" / "templates"


def test_index_template_has_documentation_map_section():
    text = (TPL / "docs" / "index.md").read_text(encoding="utf-8")
    assert "## Documentation Map" in text
    assert "Boundary rule" in text or "boundary rule" in text.lower()


def test_index_template_passes_index_map_check(tmp_path):
    # Rendered index template must itself qualify as a navigational map.
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    text = (TPL / "docs" / "index.md").read_text(encoding="utf-8").replace(
        "{{PROJECT_NAME}}", "Demo"
    )
    (docs / "index.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_index_map(tmp_path, findings)
    assert findings == []


def test_guidelines_template_has_map_section_and_pointer():
    text = (TPL / "ai-instructions" / "guidelines.en.md").read_text(encoding="utf-8")
    assert "## Documentation Map" in text
    assert "(docs/index.md)" in text  # markdown link to the map


def test_load_canonical_map_section_returns_map():
    section = adm.load_canonical_map_section()
    assert section.startswith("## Documentation Map")
    assert "docs/index.md" in section


def test_current_state_template_exists_and_is_snapshot():
    text = (TPL / "docs" / "reports" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    assert "NOT append-only" in text
    assert "Where we are" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_templates_map.py -v`
Expected: FAIL (templates lack the new content; `load_canonical_map_section` undefined)

- [ ] **Step 3: Rewrite `assets/templates/docs/index.md`**

Replace the whole file with:

```markdown
# {{PROJECT_NAME}} - Documentation

Product and engineering documentation for the project.

---

## Documentation Map

What each document and folder is for — and what does **not** belong in it.

| Document / Folder | Answers | Granularity | Cadence | Do not put here |
|---|---|---|---|---|
| This page (`index.md`) | "Where do I start / what is each doc?" | Navigation | When the structure changes | Product content |
| [Project Brief](PROJECT_BRIEF.md) | "Why does this exist, for whom?" | Vision / goal | Rarely | Requirements, technical detail |
| [Architecture](ARCHITECTURE.md) | "How is the system structured?" | Components / data | When the architecture changes | Operational state, backlog |
| [Glossary](GLOSSARY.md) | "What does this term mean?" | Domain term | When a term appears | — |
| [Decisions (ADR)](DECISIONS.md) | "Why did we decide this?" | Decision | Append per decision | Current status, plans |
| [Roadmap](ROADMAP.md) | "What is the strategy and which phase?" | Phase / milestone | When a phase changes state | Live state, changelog |
| [Backlog](BACKLOG.md) | "What is queued and at what priority?" | Item (P0/P1/P2) | When an item is born / delivered | Branch / PR / deploy state |
| [NFR](nfr/NON_FUNCTIONAL.md) | "Which non-functional requirements and ACs?" | NFR / AC-NFR | When an NFR changes | — |
| [Features](features/INDEX.md) | "Requirements, flows, rules, notes per feature" | REQ / AC per feature | When the feature evolves | Operational state |
| [Reports](reports/README.md) | "What was verified/investigated + where we are now" | Report / snapshot | Reports: per event · `CURRENT_STATE`: per session | Design truth |

> **Boundary rule.** Operational session-state — current branch, open/merged PR, deploy
> version per environment, the next physical action, the last session's narrative — is
> **not design truth**. It never goes in `ROADMAP.md`, `BACKLOG.md`, or `DECISIONS.md`.
> Narrative history lives in git history and PR descriptions. To track live state, use the
> optional snapshot `reports/CURRENT_STATE.md` (rewritten each session, never append-only).
```

(The map links all nine navigable canonical docs, so `check_index_map` passes. `CURRENT_STATE.md` is referenced in backticks only — not a markdown link — so it raises no broken-link finding.)

- [ ] **Step 4: Append the `## Documentation Map` section to `assets/templates/ai-instructions/guidelines.en.md`**

Add at the end of the file (after `## Working Principles`):

```markdown

## Documentation Map

Before writing or updating documentation, consult the map in [docs/index.md](docs/index.md) to find the right home for the content.

- **Feature work** → `docs/features/<feature>/` (README, flows, rules, notes).
- **Architectural decision** → `docs/DECISIONS.md` (ADR).
- **Strategy / phase** → `docs/ROADMAP.md`. **Queue / priority** → `docs/BACKLOG.md`.
- **Operational session-state** (branch, PR, deploy version, next action, last-session narrative) never goes in the plan docs. To track it, use the optional snapshot `docs/reports/CURRENT_STATE.md` — rewritten each session, never append-only. Narrative history lives in git and PR descriptions.
- **Do not invent new top-level docs.** If something has no home in the map, propose adding it to the map first.
```

- [ ] **Step 5: Create `assets/templates/docs/reports/CURRENT_STATE.md`**

```markdown
# Current State

> Present-state snapshot. Rewritten every session — **NOT append-only**.
> Narrative history lives in git history and PR descriptions.

## Where we are

- Branch:
- Last merge:
- Next action:

## Deploy state

- PROD:
- DEV:

## Active pending items

See [Backlog](../BACKLOG.md). Link items; do not duplicate their content.

## Open decisions

See [Decisions](../DECISIONS.md).
```

- [ ] **Step 6: Update `assets/templates/docs/reports/README.md`**

Change the `## Purpose` paragraph to note the two genres. Replace:

```markdown
## Purpose
Consolidate requirement verification reports, technical analyses, and investigations.
```

with:

```markdown
## Purpose
This folder hosts two genres: (1) point-in-time reports — requirement verification,
technical analyses, and investigations; and (2) an optional living snapshot,
`CURRENT_STATE.md`, that records where the project is right now (rewritten each session,
never append-only).
```

- [ ] **Step 7: Add scope banners to `ROADMAP.md` and `BACKLOG.md` templates**

At the top of `assets/templates/docs/ROADMAP.md`, immediately under the `# Roadmap` heading, insert:

```markdown

> Scope: strategy and delivery phases. Do not put operational session-state
> (branch / PR / deploy version) here — see the Documentation Map in `index.md`.
```

At the top of `assets/templates/docs/BACKLOG.md`, immediately under the `# Backlog` heading, insert:

```markdown

> Scope: the prioritized queue. Do not put operational session-state
> (branch / PR / deploy version) here — see the Documentation Map in `index.md`.
```

- [ ] **Step 8: Add `AI_INSTRUCTION_MAP_HEADING` and `load_canonical_map_section` to `scripts/audit_docs_model.py`**

After the `AI_INSTRUCTION_SECTION_HEADINGS` list / `CANONICAL_GUIDELINES_REL` constant (around line 51), add:

```python
AI_INSTRUCTION_MAP_HEADING = "## Documentation Map"
```

Add the loader near `load_canonical_sections` (after line 138):

```python
def load_canonical_map_section() -> str:
    text = (skill_root() / CANONICAL_GUIDELINES_REL).read_text(encoding="utf-8")
    return extract_section(text, AI_INSTRUCTION_MAP_HEADING) or ""
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_templates_map.py tests/test_index_map.py -v`
Expected: PASS (all)

- [ ] **Step 10: Commit**

```bash
git add assets/templates scripts/audit_docs_model.py tests/test_templates_map.py
git commit -m "feat: bundle documentation map templates and operational-state snapshot"
```

---

### Task 5: Plan/diff routing for the new findings

**Files:**
- Modify: `scripts/build_docs_alignment_plan.py`
- Test: `tests/test_map_plan.py` (create); `tests/test_ai_instruction_plan.py` (update one test)

`INDEX_MAP_MISSING` and `AI_INSTRUCTION_MAP_POINTER_MISSING` are neither in `CREATE_CODES` nor `IGNORE_ACTION_CODES`, so `collect_actions` already routes both to the **alter** list (no change needed there). This task adds the diff bodies: append the map block to `docs/index.md`, and append the `## Documentation Map` section to an AI-instruction file lacking the pointer.

- [ ] **Step 1: Write the failing test**

Create `tests/test_map_plan.py`:

```python
from pathlib import Path

import build_docs_alignment_plan as plan


def test_index_map_missing_routes_to_alter():
    result = {"findings": [
        {"code": "INDEX_MAP_MISSING", "path": "docs/index.md", "severity": "WARN"},
    ]}
    create, alter = plan.collect_actions(result)
    assert alter == ["docs/index.md"]
    assert create == []


def test_index_map_diff_appends_map_block(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Docs\n\nno map\n", encoding="utf-8")
    result = {"findings": [
        {"code": "INDEX_MAP_MISSING", "path": "docs/index.md",
         "severity": "WARN", "message": "no map"},
    ]}
    items, deferred = plan.proposed_diffs(tmp_path, result, [], ["docs/index.md"], 10)
    index_items = [it for it in items if it["path"] == "docs/index.md"]
    assert len(index_items) == 1
    assert index_items[0]["type"] == "update"
    assert "## Documentation Map" in index_items[0]["diff"]


def test_pointer_missing_diff_appends_map_section(tmp_path):
    # CLAUDE.md has workflow + principles but no docs/index.md pointer.
    import audit_docs_model as adm
    sections = adm.load_canonical_sections()
    text = "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS) + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "## Documentation Map" in diff
    assert "docs/index.md" in diff
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_map_plan.py -v`
Expected: FAIL — `test_index_map_diff_appends_map_block` produces a generic `update-plan` diff without the map; `test_pointer_missing_diff_appends_map_section` returns "No changes required."

- [ ] **Step 3: Add the `index.md` map-append diff generator**

In `scripts/build_docs_alignment_plan.py`, add after `feature_section_append_diff` (after line 158):

```python
def index_map_append_diff(repo: Path, target_rel: str) -> str:
    template = templates_root() / "docs" / "index.md"
    section = adm.extract_section(template.read_text(encoding="utf-8"), "## Documentation Map")
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    return _append_block_diff(target_rel, text.splitlines(), section or "")
```

- [ ] **Step 4: Extend `ai_instruction_update_diff` to append the map section when the pointer is missing**

In `ai_instruction_update_diff` (lines 161-180), after the `has_principles` block and before the `return`, add the pointer branch:

```python
    if not has_principles:
        blocks.append(_append_block_diff(target_rel, file_lines, canonical["## Working Principles"], label))
    if not adm.references_doc_index(file_path, repo):
        map_section = adm.load_canonical_map_section()
        if map_section:
            blocks.append(_append_block_diff(target_rel, file_lines, map_section, label))

    return "\n\n".join(blocks) if blocks else "No changes required."
```

- [ ] **Step 5: Route `INDEX_MAP_MISSING` in `proposed_diffs`**

In `proposed_diffs`, inside the `for target_rel in alter_files:` loop, add this branch as the FIRST check inside the loop (before the `AI_INSTRUCTION_FILES` check, around line 282):

```python
    for target_rel in alter_files:
        if len(items) >= max_diffs:
            break
        if any(
            f["path"] == target_rel and f["code"] == "INDEX_MAP_MISSING"
            for f in result["findings"]
        ):
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": index_map_append_diff(repo, target_rel),
                }
            )
            continue
        if target_rel in AI_INSTRUCTION_FILES:
            ...
```

(Keep the existing `AI_INSTRUCTION_FILES`, `feature_gaps`, and fallback branches unchanged below it.)

- [ ] **Step 6: Update the now-stale identical-file plan test**

In `tests/test_ai_instruction_plan.py`, `test_ai_instruction_update_diff_identical_file_reports_no_changes` writes only workflow+principles (no pointer), which now appends the map section. Update the fixture to include the pointer so a fully canonical file yields no changes:

```python
def test_ai_instruction_update_diff_identical_file_reports_no_changes(tmp_path):
    sections = adm.load_canonical_sections()
    text = "# Project\n\nSee [docs/index.md](docs/index.md).\n\n" + "\n\n".join(
        sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS
    ) + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert diff == "No changes required."
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_map_plan.py tests/test_ai_instruction_plan.py -v`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add scripts/build_docs_alignment_plan.py tests/test_map_plan.py tests/test_ai_instruction_plan.py
git commit -m "feat: propose documentation-map diffs for index.md and AI-instruction files"
```

---

### Task 6: Update reference, spec, and skill docs

**Files:**
- Modify: `references/docs-model-spec.md`
- Modify: `references/compliance-rules.md`
- Modify: `SKILL.md`
- Modify: `README.md`

No tests; documentation only. Keep wording consistent with the new behavior.

- [ ] **Step 1: `references/docs-model-spec.md` — add the ownership map section**

After the `## Canonical Required Files` block, add:

```markdown
## Documentation Ownership Map

`docs/index.md` must be a navigational map: it links to a strict majority of the
navigable canonical docs (the required set minus `index.md`, `requirements-mkdocs.txt`,
and `mkdocs.yml`) and states, for each doc/folder, what it answers and what must not go in
it. In alignment mode, an `index.md` that is not such a map is `WARN` (`INDEX_MAP_MISSING`);
the richness of the map columns is not audited.

**Boundary rule.** Operational session-state (current branch, open/merged PR, deploy
version per environment, next physical action, last-session narrative) is not design
truth. It never goes in `ROADMAP.md`, `BACKLOG.md`, or `DECISIONS.md`. Narrative history
lives in git history and PR descriptions.

**Optional operational snapshot.** `docs/reports/CURRENT_STATE.md` is an optional living
snapshot (rewritten each session, never append-only). It is not a required file; its
absence is never a finding. The skill never auto-creates it.
```

In the `## AI Instruction Files` section, add a sentence:

```markdown
Existing AI-instruction files should also link to `docs/index.md` (the documentation map).
A missing pointer is reported as `INFO` (`AI_INSTRUCTION_MAP_POINTER_MISSING`); it is never
a `BLOCKER` and the structural shape detection is unchanged.
```

- [ ] **Step 2: `references/compliance-rules.md` — add the new rules**

After `R012`, add:

```markdown
### R013 Documentation map present (WARN)

`docs/index.md` must link to a strict majority of the navigable canonical docs
(`PROJECT_BRIEF`, `ARCHITECTURE`, `GLOSSARY`, `DECISIONS`, `ROADMAP`, `BACKLOG`,
`nfr/NON_FUNCTIONAL`, `features/INDEX`, `reports/README`). Detection is by resolved link
target (language-agnostic). Otherwise report `WARN` (`INDEX_MAP_MISSING`). Absent
`index.md` is covered by R001, not here.

### R014 AI instruction map pointer (INFO)

An existing AI-instruction file that does not link to `docs/index.md` is reported as `INFO`
(`AI_INSTRUCTION_MAP_POINTER_MISSING`). Never a `BLOCKER`.

### R015 Optional operational snapshot

`docs/reports/CURRENT_STATE.md` is optional. Its absence is never a finding; the skill
never creates it.
```

In `## Classification Rules`, add:

```markdown
- Missing documentation map in `index.md` => `WARN`
- Missing `docs/index.md` pointer in an AI-instruction file => `INFO`
```

- [ ] **Step 2b: `references/compliance-rules.md` — extend the evaluation scope**

Under `## Evaluation Scope`, the current list mentions `mkdocs.yml`, `docs/**/*.md`, and `docs/requirements-mkdocs.txt`. Add a line so the AI-instruction pointer rule's scope is explicit:

```markdown
- existing AI-instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`)
```

- [ ] **Step 3: `SKILL.md` — document the map in the Canonical Model defaults**

In the `## Canonical Model` "Apply these defaults" list, add a bullet:

```markdown
- `docs/index.md` is a navigational ownership map (what each doc/folder is for and what must not go in it); operational session-state (branch/PR/deploy) is not design truth and lives in git/PRs or the optional `docs/reports/CURRENT_STATE.md` snapshot — never in ROADMAP/BACKLOG/DECISIONS
- Alignment adds: `INDEX_MAP_MISSING` (`WARN`) when `index.md` is not a map, and `AI_INSTRUCTION_MAP_POINTER_MISSING` (`INFO`) when an existing AI-instruction file lacks a `docs/index.md` pointer; `CURRENT_STATE.md` is optional and never created
```

- [ ] **Step 4: `README.md` — describe the self-describing model**

In the "Canonical documentation model" tree, add `CURRENT_STATE.md` under `reports/`:

```markdown
├── reports/
│   ├── README.md               # Reports index
│   └── CURRENT_STATE.md        # Optional living state snapshot (rewritten each session)
```

After the "Traceability rules" block, add a short subsection:

```markdown
### Documentation map and operational state

`docs/index.md` is a navigational map: it documents what each file/folder answers and what
must not go in it. Operational session-state (branch, PR, deploy version, next action) is
not design truth — it never goes in ROADMAP/BACKLOG/DECISIONS; it lives in git/PRs or, if
you want a readable "where are we now" pointer, in the optional `docs/reports/CURRENT_STATE.md`
snapshot (rewritten each session, never append-only). In alignment mode the skill warns
(`INDEX_MAP_MISSING`) when `index.md` is not a map and infos
(`AI_INSTRUCTION_MAP_POINTER_MISSING`) when an existing AI-instruction file lacks a pointer
to the map.
```

- [ ] **Step 5: Run the full suite one more time**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add references/docs-model-spec.md references/compliance-rules.md SKILL.md README.md
git commit -m "docs: document self-describing docs model, map rules, and operational-state home"
```

---

## Self-Review Notes

- **Spec coverage:** §1 durable map → Tasks 1, 4; §2 AI-instruction directive + pointer → Tasks 2, 4, 5; §3 optional snapshot → Tasks 3, 4; severity map → Tasks 1, 2; plan/diff → Task 5; components/files (spec list) → Tasks 1-6; out-of-scope items honored (no required STATUS, no third structural shape, no auto-create, no column-richness audit).
- **No retroactive BLOCKER:** the pointer finding is INFO; `detect_ai_instruction_shapes` is untouched. Projects on the old `index.md` template link all nine docs, so `INDEX_MAP_MISSING` does not fire on them.
- **Type/name consistency:** `check_index_map`, `references_doc_index`, `load_canonical_map_section`, `AI_INSTRUCTION_MAP_HEADING`, `INDEX_MAP_NAVIGABLE`, `index_map_append_diff` are used with identical names across audit, plan, and tests. Finding codes `INDEX_MAP_MISSING` / `AI_INSTRUCTION_MAP_POINTER_MISSING` are consistent everywhere.
- **Updated existing tests:** `test_identical_file_produces_no_finding`, `test_copilot_nested_path_detected` (Task 2), and `test_ai_instruction_update_diff_identical_file_reports_no_changes` (Task 5) — each updated because the new pointer behavior legitimately changes their expected output.
```