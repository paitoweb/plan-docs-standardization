# AI Instruction Files Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a planning-only capability that audits existing AI instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) and proposes diffs aligning them to a canonical English guidelines block — never creating the files, never applying edits.

**Architecture:** A single English template holds the canonical guidelines (two `##` sections). `audit_docs_model.py` gains section-extraction/normalization helpers and a new `check_ai_instruction_files()` that emits INFO for absent files and BLOCKER for missing/divergent sections. `build_docs_alignment_plan.py` excludes absent files from create/alter, emits real add/replace diffs for the AI instruction sections, and lists absent files in a dedicated note. Reference specs and SKILL/README are updated.

**Tech Stack:** Python 3.12, pytest 7.4.4, PyYAML. No new dependencies.

---

## File Structure

**Create:**
- `assets/templates/ai-instructions/guidelines.en.md` — canonical guidelines block (single source of truth).
- `tests/conftest.py` — adds `scripts/` to `sys.path` for imports.
- `tests/test_ai_instruction_audit.py` — audit-side tests.
- `tests/test_ai_instruction_plan.py` — plan/diff-side tests.

**Modify:**
- `scripts/audit_docs_model.py` — constants, `section_span`/`extract_section`/`normalize_block`/`load_canonical_sections` helpers, `check_ai_instruction_files`, wiring.
- `scripts/build_docs_alignment_plan.py` — action exclusion, AI instruction diff builder, absent-files note.
- `references/compliance-rules.md` — rules R010/R011 + non-creation note.
- `references/docs-model-spec.md` — "AI Instruction Files" section.
- `SKILL.md` — document the capability.
- `README.md` — user-facing description.

---

## Task 1: Canonical guidelines template

**Files:**
- Create: `assets/templates/ai-instructions/guidelines.en.md`
- Create: `tests/conftest.py`
- Test: `tests/test_ai_instruction_audit.py`

- [ ] **Step 1: Create the conftest so tests can import the scripts**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
```

- [ ] **Step 2: Write the failing test for the template**

Create `tests/test_ai_instruction_audit.py`:

```python
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "templates" / "ai-instructions" / "guidelines.en.md"


def test_canonical_template_exists_with_two_sections():
    assert TEMPLATE.exists(), "canonical guidelines template must exist"
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Workflow: New Feature" in text
    assert "## Working Principles" in text
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py::test_canonical_template_exists_with_two_sections -v`
Expected: FAIL (template file does not exist yet).

- [ ] **Step 4: Create the canonical template**

Create `assets/templates/ai-instructions/guidelines.en.md` with EXACTLY this content:

```markdown
## Workflow: New Feature

Steps in order — each typically corresponds to one interaction. Steps may be combined when the feature is small.

**IMPORTANT**: Before advancing to any step, verify that the previous ones were completed. If the user asks to implement without docs, requirements, and a plan in place, question it and guide them back to the correct step.

1. **Brainstorm** — align intent and technical choices with the user (skill `superpowers:brainstorming` or similar; using a skill is optional).
2. **Spec** — create the feature structure under `docs/features/<feature>/` (if it does not exist) and write it with concrete REQs/ACs.
3. **Plan** — analyze the documentation and create an implementation plan (skill `superpowers:writing-plans` or similar; using a skill is optional).
4. **Review** — review and approve the plan with the user.
5. **Implementation** — implement the approved plan, using TDD when applicable.
6. **Document** — update `ROADMAP.md` and `BACKLOG.md` if it makes sense, `DECISIONS.md` and `ARCHITECTURE.md` if the decision is architectural, any other documents needed based on the completed implementation, and whatever the feature needs under `docs/features/<feature>/`.
7. **Tests** — create/update tests (following the traceability principle) and validate (define the method/stack with the user).
8. **Commit & PR** — commit following the conventions and open a PR referencing REQ-AC and linking to the feature doc (`docs/features/<feature>/`).

## Working Principles

They complement the project's "non-negotiable invariants" and "NOT list". They are stances, not technical rules:

- **Clarify before implementing**: when in doubt, ask — never assume product requirements, technical requirements, engineering principles, or hard constraints.
- **Distinguish assumption from fact**: make explicit when something is your own conclusion, a hypothesis, or an assumption vs. established project data/rule.
- **Official docs for APIs**: for libraries and SDKs, rely only on official documentation — never assume signatures, methods, or behaviors.
- **Pragmatism**: be practical and direct. Do not invent out-of-scope features. Do not ramble.
- **traceability**: traceability is mandatory at three ends: documented requirement (`REQ-*` under `docs/features/`), **source code that implements a REQ cites the ID** (function/constant JSDoc or file header), and tests include a `// Traceability:` comment pointing to the doc.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py::test_canonical_template_exists_with_two_sections -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assets/templates/ai-instructions/guidelines.en.md tests/conftest.py tests/test_ai_instruction_audit.py
git commit -m "feat: add canonical AI instruction guidelines template"
```

---

## Task 2: Section helpers in audit_docs_model.py

Adds pure helpers used by both audit and plan: locate a `##` section span, extract its text, normalize a block, and load the canonical sections from the template.

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_ai_instruction_audit.py`

- [ ] **Step 1: Write the failing tests for the helpers**

Append to `tests/test_ai_instruction_audit.py`:

```python
import audit_docs_model as adm


def test_section_span_finds_level2_section():
    text = "# Title\n\n## A\nbody a\n\n## B\nbody b\n"
    lines = text.splitlines()
    assert adm.section_span(lines, "## A") == (2, 5)
    assert adm.section_span(lines, "## B") == (5, 7)
    assert adm.section_span(lines, "## Missing") is None


def test_section_span_stops_at_next_level2_not_level3():
    text = "## A\nbody\n### Sub\nmore\n## B\n"
    lines = text.splitlines()
    start, end = adm.section_span(lines, "## A")
    assert lines[start:end] == ["## A", "body", "### Sub", "more"]


def test_extract_section_returns_text_or_none():
    text = "## A\nbody a\n## B\nbody b\n"
    assert adm.extract_section(text, "## A") == "## A\nbody a"
    assert adm.extract_section(text, "## Z") is None


def test_normalize_block_collapses_blanks_and_trims():
    raw = "  ## A  \n\n\nbody\n\n"
    assert adm.normalize_block(raw) == "## A\n\nbody"


def test_load_canonical_sections_returns_two_sections():
    sections = adm.load_canonical_sections()
    assert set(sections) == {"## Workflow: New Feature", "## Working Principles"}
    assert sections["## Workflow: New Feature"].startswith("## Workflow: New Feature")
    assert "traceability" in sections["## Working Principles"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py -v -k "section or normalize or canonical"`
Expected: FAIL with `AttributeError: module 'audit_docs_model' has no attribute 'section_span'`.

- [ ] **Step 3: Add the constants**

In `scripts/audit_docs_model.py`, after the `FEATURE_REQUIRED_FILES` line (currently line 37), add:

```python
AI_INSTRUCTION_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]

AI_INSTRUCTION_SECTION_HEADINGS = [
    "## Workflow: New Feature",
    "## Working Principles",
]

CANONICAL_GUIDELINES_REL = "assets/templates/ai-instructions/guidelines.en.md"
```

- [ ] **Step 4: Add the helper functions**

In `scripts/audit_docs_model.py`, add these functions right after `normalize_text` (currently ends at line 84):

```python
def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def section_span(lines: list[str], heading: str) -> tuple[int, int] | None:
    """Return (start, end) line indices of a level-2 section, end exclusive."""

    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].lstrip().startswith("## "):
            end = index
            break
    return start, end


def extract_section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    span = section_span(lines, heading)
    if span is None:
        return None
    start, end = span
    return "\n".join(lines[start:end])


def normalize_block(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    collapsed: list[str] = []
    for line in lines:
        if not line and collapsed and not collapsed[-1]:
            continue
        collapsed.append(line)
    return "\n".join(collapsed)


def load_canonical_sections() -> dict[str, str]:
    template_path = skill_root() / CANONICAL_GUIDELINES_REL
    text = template_path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for heading in AI_INSTRUCTION_SECTION_HEADINGS:
        section = extract_section(text, heading)
        if section is None:
            raise ValueError(f"Canonical template missing section: {heading}")
        sections[heading] = section
    return sections
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py -v -k "section or normalize or canonical"`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_ai_instruction_audit.py
git commit -m "feat: add section extraction and canonical loading helpers"
```

---

## Task 3: check_ai_instruction_files and wiring

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_ai_instruction_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai_instruction_audit.py`:

```python
def _canonical_text():
    sections = adm.load_canonical_sections()
    return "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)


def _codes_for(findings, path):
    return {f.code for f in findings if f.path == path}


def test_absent_files_report_info(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    info_codes = {f.code for f in findings if f.severity == "INFO"}
    assert info_codes == {"AI_INSTRUCTION_FILE_ABSENT"}
    absent_paths = {f.path for f in findings}
    assert absent_paths == set(adm.AI_INSTRUCTION_FILES)


def test_identical_file_produces_no_finding(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n" + _canonical_text() + "\n", encoding="utf-8"
    )
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert _codes_for(findings, "CLAUDE.md") == set()


def test_missing_section_is_blocker(tmp_path):
    sections = adm.load_canonical_sections()
    only_first = sections["## Workflow: New Feature"]
    (tmp_path / "CLAUDE.md").write_text(only_first + "\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md" and f.severity == "BLOCKER"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert "Working Principles" in blockers[0].message


def test_divergent_section_is_blocker(tmp_path):
    sections = adm.load_canonical_sections()
    tampered = sections["## Working Principles"].replace("Pragmatism", "Pragmatism CHANGED")
    text = sections["## Workflow: New Feature"] + "\n\n" + tampered + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = _codes_for(findings, "CLAUDE.md")
    assert codes == {"AI_INSTRUCTION_SECTION_DIVERGENT"}


def test_copilot_nested_path_detected(tmp_path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "copilot-instructions.md").write_text("# x\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = _codes_for(findings, ".github/copilot-instructions.md")
    assert codes == {"AI_INSTRUCTION_SECTION_MISSING"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py -v -k "absent or identical or missing_section or divergent or copilot"`
Expected: FAIL with `AttributeError: ... has no attribute 'check_ai_instruction_files'`.

- [ ] **Step 3: Add the check function**

In `scripts/audit_docs_model.py`, add after `check_mkdocs_nav` (currently ends at line 509):

```python
def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
    canonical = load_canonical_sections()

    for rel in AI_INSTRUCTION_FILES:
        path = repo / rel
        if not path.exists():
            make_finding(
                findings,
                "INFO",
                "AI_INSTRUCTION_FILE_ABSENT",
                rel,
                "AI instruction file absent; skill does not create it. "
                "Create it manually to receive the canonical guidelines.",
            )
            continue

        text = path.read_text(encoding="utf-8")
        for heading in AI_INSTRUCTION_SECTION_HEADINGS:
            file_section = extract_section(text, heading)
            if file_section is None:
                make_finding(
                    findings,
                    "BLOCKER",
                    "AI_INSTRUCTION_SECTION_MISSING",
                    rel,
                    f"AI instruction file missing canonical section: {heading}",
                )
                continue
            if normalize_block(file_section) != normalize_block(canonical[heading]):
                make_finding(
                    findings,
                    "BLOCKER",
                    "AI_INSTRUCTION_SECTION_DIVERGENT",
                    rel,
                    f"AI instruction section diverges from canonical: {heading}",
                )
```

- [ ] **Step 4: Wire it into audit_repository**

In `scripts/audit_docs_model.py`, inside `audit_repository`, after the `check_mkdocs_nav(repo, findings)` call (currently line 554), add:

```python
    check_ai_instruction_files(repo, findings)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ai_instruction_audit.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_ai_instruction_audit.py
git commit -m "feat: audit AI instruction files for canonical guidelines"
```

---

## Task 4: Plan generation — exclude absent, emit real diffs, add note

**Files:**
- Modify: `scripts/build_docs_alignment_plan.py`
- Test: `tests/test_ai_instruction_plan.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai_instruction_plan.py`:

```python
import audit_docs_model as adm
import build_docs_alignment_plan as plan


def _canonical_text():
    sections = adm.load_canonical_sections()
    return "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS)


def test_absent_finding_excluded_from_actions():
    result = {
        "findings": [
            {"code": "AI_INSTRUCTION_FILE_ABSENT", "path": "CLAUDE.md", "severity": "INFO"},
            {"code": "MISSING_REQUIRED_FILE", "path": "docs/index.md", "severity": "BLOCKER"},
        ]
    }
    create, alter = plan.collect_actions(result)
    assert "CLAUDE.md" not in create
    assert "CLAUDE.md" not in alter
    assert "docs/index.md" in create


def test_blocker_ai_finding_goes_to_alter():
    result = {
        "findings": [
            {"code": "AI_INSTRUCTION_SECTION_MISSING", "path": "AGENTS.md", "severity": "BLOCKER"},
        ]
    }
    create, alter = plan.collect_actions(result)
    assert alter == ["AGENTS.md"]
    assert create == []


def test_ai_instruction_update_diff_appends_missing_section(tmp_path):
    sections = adm.load_canonical_sections()
    (tmp_path / "CLAUDE.md").write_text(
        sections["## Workflow: New Feature"] + "\n", encoding="utf-8"
    )
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "+## Working Principles" in diff
    assert "## Workflow: New Feature" not in diff.replace("+## Working Principles", "")


def test_ai_instruction_update_diff_replaces_divergent_section(tmp_path):
    sections = adm.load_canonical_sections()
    tampered = sections["## Working Principles"].replace("Pragmatism", "Pragmatism CHANGED")
    text = sections["## Workflow: New Feature"] + "\n\n" + tampered + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "-- **Pragmatism CHANGED**" in diff or "-- **Pragmatism CHANGED**: " in diff
    assert "+- **Pragmatism**" in diff


def test_build_markdown_lists_absent_ai_files(tmp_path):
    result = {
        "mode": "alignment",
        "summary": {"blocker": 0, "warn": 0, "info": 1},
        "findings": [
            {"code": "AI_INSTRUCTION_FILE_ABSENT", "path": "GEMINI.md",
             "severity": "INFO", "message": "absent"},
        ],
    }
    md = plan.build_markdown(tmp_path, result, [], [], [], [])
    assert "AI Instruction Files Absent" in md
    assert "`GEMINI.md`" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ai_instruction_plan.py -v`
Expected: FAIL (`collect_actions` still lists absent file; `ai_instruction_update_diff` missing; `build_markdown` takes 6 args without absent section).

- [ ] **Step 3: Add the action-exclusion and AI file constants**

In `scripts/build_docs_alignment_plan.py`, after the `CREATE_CODES` line (currently line 23), add:

```python
IGNORE_ACTION_CODES = {"AI_INSTRUCTION_FILE_ABSENT"}
AI_INSTRUCTION_FILES = set(adm.AI_INSTRUCTION_FILES)
```

- [ ] **Step 4: Update collect_actions to skip ignored codes**

In `scripts/build_docs_alignment_plan.py`, replace the loop body in `collect_actions` (currently lines 155-163). The current code is:

```python
    for finding in result["findings"]:
        path = finding["path"]
        code = finding["code"]

        if code in CREATE_CODES:
            create.add(path)
        else:
            alter.add(path)
```

Replace with:

```python
    for finding in result["findings"]:
        path = finding["path"]
        code = finding["code"]

        if code in IGNORE_ACTION_CODES:
            continue
        if code in CREATE_CODES:
            create.add(path)
        else:
            alter.add(path)
```

- [ ] **Step 5: Add the AI instruction diff builder**

In `scripts/build_docs_alignment_plan.py`, add after `placeholder_update_diff` (currently ends at line 129):

```python
def _section_diff_block(target_rel: str, file_lines: list[str], heading: str, canonical_section: str) -> str | None:
    span = adm.section_span(file_lines, heading)
    new_lines = canonical_section.splitlines()

    if span is None:
        start = len(file_lines)
        added = [""] + new_lines
        header = f"@@ -{start},0 +{start + 1},{len(added)} @@"
        body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
        body.extend(f"+{line}" for line in added)
        return "\n".join(body)

    start, end = span
    old_lines = file_lines[start:end]
    if adm.normalize_block("\n".join(old_lines)) == adm.normalize_block(canonical_section):
        return None

    header = f"@@ -{start + 1},{len(old_lines)} +{start + 1},{len(new_lines)} @@"
    body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
    body.extend(f"-{line}" for line in old_lines)
    body.extend(f"+{line}" for line in new_lines)
    return "\n".join(body)


def ai_instruction_update_diff(repo: Path, target_rel: str) -> str:
    canonical = adm.load_canonical_sections()
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    file_lines = text.splitlines()

    blocks: list[str] = []
    for heading in adm.AI_INSTRUCTION_SECTION_HEADINGS:
        block = _section_diff_block(target_rel, file_lines, heading, canonical[heading])
        if block:
            blocks.append(block)

    return "\n\n".join(blocks) if blocks else "No changes required."
```

- [ ] **Step 6: Route AI instruction files through the new builder in proposed_diffs**

In `scripts/build_docs_alignment_plan.py`, in `proposed_diffs`, replace the alter loop (currently lines 224-234). The current code is:

```python
    for target_rel in alter_files:
        if len(items) >= max_diffs:
            break
        reasons = grouped_reasons.get(target_rel, ["Update to comply with the canonical model"])  # pragma: no cover
        items.append(
            {
                "path": target_rel,
                "type": "update-plan",
                "diff": placeholder_update_diff(target_rel, reasons),
            }
        )
```

Replace with:

```python
    for target_rel in alter_files:
        if len(items) >= max_diffs:
            break
        if target_rel in AI_INSTRUCTION_FILES:
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": ai_instruction_update_diff(repo, target_rel),
                }
            )
            continue
        reasons = grouped_reasons.get(target_rel, ["Update to comply with the canonical model"])  # pragma: no cover
        items.append(
            {
                "path": target_rel,
                "type": "update-plan",
                "diff": placeholder_update_diff(target_rel, reasons),
            }
        )
```

- [ ] **Step 7: Add the absent-files note to build_markdown (derived from findings)**

In `scripts/build_docs_alignment_plan.py`, keep the `build_markdown` signature unchanged. Immediately before the `lines.append("")` that precedes `## Proposed Diffs` (currently line 319, the blank line right after the Alter list block), insert:

```python
    absent_ai_files = [
        finding["path"]
        for finding in result["findings"]
        if finding.get("code") == "AI_INSTRUCTION_FILE_ABSENT"
    ]
    lines.append("")
    lines.append("### AI Instruction Files Absent (not created by design)")
    if absent_ai_files:
        for path in absent_ai_files:
            lines.append(f"- `{path}`: present-only check; create manually to receive guidelines.")
    else:
        lines.append("- None")
```

Deriving the list inside `build_markdown` keeps the signature stable, so the test can call it with the standard six arguments and still see the absent files.

- [ ] **Step 8: Expose absent files in the JSON output**

In `scripts/build_docs_alignment_plan.py`, in `main`, after the `diffs, deferred_create = proposed_diffs(...)` call (currently ends line 357), add:

```python
    absent_ai_files = [
        finding["path"]
        for finding in audit_result["findings"]
        if finding["code"] == "AI_INSTRUCTION_FILE_ABSENT"
    ]
```

Then add `absent_ai_files` to the `output` dict (currently lines 359-368) by inserting this line inside the dict literal after `"diffs": diffs,`:

```python
        "absent_ai_files": absent_ai_files,
```

Leave the markdown print call unchanged (it now derives the absent list internally).

- [ ] **Step 9: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ai_instruction_plan.py -v`
Expected: PASS (all tests).

- [ ] **Step 10: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all tests from Tasks 1–4).

- [ ] **Step 11: Commit**

```bash
git add scripts/build_docs_alignment_plan.py tests/test_ai_instruction_plan.py
git commit -m "feat: propose AI instruction file diffs and list absent files"
```

---

## Task 5: Update reference specs

**Files:**
- Modify: `references/compliance-rules.md`
- Modify: `references/docs-model-spec.md`

- [ ] **Step 1: Add rules R010/R011 to compliance-rules.md**

In `references/compliance-rules.md`, after the `### R009 Optional quality observations (WARN/INFO)` block (ends line 65), add:

```markdown
### R010 AI instruction section missing (BLOCKER)

For each existing AI instruction file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`), a missing canonical section
(`## Workflow: New Feature` or `## Working Principles`) is non-compliant.

### R011 AI instruction section divergent (BLOCKER)

If a canonical section is present but its normalized content differs from the
canonical guidelines block, it is non-compliant.

### R012 AI instruction file absent (INFO)

If an AI instruction file does not exist, report it as INFO only. The skill never
creates these files.
```

- [ ] **Step 2: Add the non-creation note to the Non-Mutation Constraint section**

In `references/compliance-rules.md`, inside `## Non-Mutation Constraint`, after the existing bullet list (ends line 96), add:

```markdown
Additionally, the skill must never create AI instruction files. For absent
`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.github/copilot-instructions.md`, output only an
INFO finding instructing manual creation.
```

- [ ] **Step 3: Add the AI Instruction Files section to docs-model-spec.md**

In `references/docs-model-spec.md`, after the `## Non-canonical Artifacts To Ignore` section (ends line 69), add:

```markdown
## AI Instruction Files (optional, never created)

The skill optionally aligns AI instruction files when they already exist. It never
creates them.

Target files (repository root, plus the GitHub path):

- `CLAUDE.md`
- `AGENTS.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`

Canonical guidelines block (single source of truth, English only):

- `assets/templates/ai-instructions/guidelines.en.md`

It defines two sections, located by title:

- `## Workflow: New Feature`
- `## Working Principles`

For an existing file: a missing section or a section whose normalized content diverges
from the canonical block is a `BLOCKER`; an absent file is `INFO`.
```

- [ ] **Step 4: Verify the references mention the new rules**

Run: `grep -n "R010\|R011\|R012\|AI Instruction Files\|guidelines.en.md" references/compliance-rules.md references/docs-model-spec.md`
Expected: matches in both files.

- [ ] **Step 5: Commit**

```bash
git add references/compliance-rules.md references/docs-model-spec.md
git commit -m "docs: document AI instruction file rules in references"
```

---

## Task 6: Update SKILL.md and README.md

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Document the capability in SKILL.md**

In `SKILL.md`, after the `## Template Usage` section (ends line 116, just before `## Escalation Policy`), add:

```markdown
## AI Instruction Files Alignment

Optionally align existing AI instruction files to the canonical guidelines block.

- Target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`.
- Canonical block (English only): `assets/templates/ai-instructions/guidelines.en.md`,
  with sections `## Workflow: New Feature` and `## Working Principles`.
- Never create these files. If absent, emit an `INFO` finding instructing manual creation.
- If a file exists, missing or divergent canonical sections are `BLOCKER`; propose a diff
  that appends the missing section or replaces the divergent one. Never apply changes.
```

- [ ] **Step 2: Add the defaults note in SKILL.md**

In `SKILL.md`, under `## Operating Modes` → the `alignment` bullet, no change needed. Instead, in the `Apply these defaults:` list (ends line 43), add a bullet:

```markdown
- AI instruction files are optional and never created; only existing ones are audited and proposed for alignment
```

- [ ] **Step 3: Document the feature in README.md**

In `README.md`, after the `### Traceability rules` block (ends line 70), add a new subsection:

```markdown
## AI instruction files alignment

The skill can align existing AI instruction files to a canonical guidelines block:

- Target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`
- Canonical block (English): `assets/templates/ai-instructions/guidelines.en.md`,
  containing a **Workflow: New Feature** section and a **Working Principles** section.

Behavior:

- The skill **never creates** these files. If a file is absent, it reports INFO and asks
  you to create it manually.
- For an existing file, a missing or divergent canonical section is a BLOCKER, and the
  skill proposes a diff (never applied) to add or restore the canonical block.
```

- [ ] **Step 4: Verify the docs mention the capability**

Run: `grep -n "AI [Ii]nstruction" SKILL.md README.md`
Expected: matches in both files.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md README.md
git commit -m "docs: document AI instruction files alignment in SKILL and README"
```

---

## Task 7: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 2: Smoke-test the audit script against a temp repo with a partial CLAUDE.md**

Run:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/docs"
printf '## Workflow: New Feature\nbody\n' > "$TMP/CLAUDE.md"
python3 scripts/audit_docs_model.py "$TMP" --format json | python3 -c "import sys,json; d=json.load(sys.stdin); print([f for f in d['findings'] if f['code'].startswith('AI_INSTRUCTION')])"
```

Expected: one `AI_INSTRUCTION_SECTION_MISSING` for `CLAUDE.md` (Working Principles) and three `AI_INSTRUCTION_FILE_ABSENT` for the other files.

- [ ] **Step 3: Smoke-test the plan script shows a real diff**

Run:

```bash
python3 scripts/build_docs_alignment_plan.py "$TMP" | sed -n '/Proposed Diffs/,$p' | head -40
rm -rf "$TMP"
```

Expected: a `### update: \`CLAUDE.md\`` block whose diff contains `+## Working Principles`, plus an "AI Instruction Files Absent" note listing the other three files.

- [ ] **Step 4: Confirm no regressions in existing output contract**

Run: `python3 scripts/build_docs_alignment_plan.py . | grep -E "Executive Summary|Compliance Matrix|Immediate Alignment Plan|File Create/Alter List|Proposed Diffs"`
Expected: all five canonical sections present.
```
