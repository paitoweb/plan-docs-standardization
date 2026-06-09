# Language-Agnostic Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make alignment-mode compliance language-agnostic by inferring expectations from the project's own docs — reference-based feature-section consistency and structural detection of AI-instruction sections — eliminating false BLOCKERs on non-English documentation.

**Architecture:** `audit_docs_model.py` gains pure section-title helpers, a reference-based feature-section consistency check (replacing the fixed English seven-section check), and structural shape detection for AI-instruction files (replacing English-heading + divergence checks). `build_docs_alignment_plan.py` proposes the reference's heading text for missing feature sections and the English canonical block as a labeled starting point for missing AI sections. Skill/templates stay English; bootstrap stays English.

**Tech Stack:** Python 3.12, pytest 7.4.4. No new dependencies.

---

## File Structure

**Modify:**
- `scripts/audit_docs_model.py` — add section-title + level-2-section helpers; add `compute_feature_section_gaps` + `check_feature_section_consistency`; remove `FEATURE_README_REQUIRED_HEADINGS`, `heading_lines`, and the `MISSING_README_SECTION` block; add `detect_ai_instruction_shapes`; rewrite `check_ai_instruction_files`; remove `AI_INSTRUCTION_SECTION_DIVERGENT`.
- `scripts/build_docs_alignment_plan.py` — add `_append_block_diff`, `feature_section_append_diff`; rewrite `ai_instruction_update_diff`; route feature-section gaps in `proposed_diffs`; remove dead `_section_diff_block`.
- `references/compliance-rules.md`, `references/docs-model-spec.md`, `SKILL.md`, `README.md` — document the language-agnostic behavior.

**Create / update tests:**
- `tests/test_language_agnostic.py` — new: section-title helpers, feature-section consistency, AI structural detection, plan diffs.
- `tests/test_ai_instruction_audit.py` — rewrite the missing-section test, remove the divergence test.
- `tests/test_ai_instruction_plan.py` — remove the divergence test (others stay valid).

---

## Task 1: Section-title and level-2-section helpers

Pure functions used by both the feature-section and AI-instruction checks.

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_language_agnostic.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_language_agnostic.py`:

```python
import audit_docs_model as adm


def test_normalize_section_title_strips_accents_paren_and_case():
    assert adm.normalize_section_title("Visão Geral") == "visao geral"
    assert adm.normalize_section_title("Requisitos (REQ-*)") == "requisitos"
    assert adm.normalize_section_title("  Acceptance   Criteria (AC-*) ") == "acceptance criteria"


def test_feature_section_titles_dedup_and_skip_level3():
    text = "# T\n\n## Visão Geral\nx\n\n## Requisitos (REQ-*)\n### AC-FOO-001\n## Visão Geral\n"
    titles = adm.feature_section_titles(text)
    assert titles == [("visao geral", "Visão Geral"), ("requisitos", "Requisitos (REQ-*)")]


def test_iter_level2_sections_splits_on_level2_only():
    text = "## A\nbody\n### Sub\nmore\n## B\nb2\n"
    sections = adm.iter_level2_sections(text)
    assert sections == [["## A", "body", "### Sub", "more"], ["## B", "b2"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_language_agnostic.py -v`
Expected: FAIL with `AttributeError: module 'audit_docs_model' has no attribute 'normalize_section_title'`.

- [ ] **Step 3: Add the regexes**

In `scripts/audit_docs_model.py`, after the `AC_NFR_HEADING_RE = ...` line (currently line 64), add:

```python
SECTION_HEADING_RE = re.compile(r"^\s*##\s+(.*\S)\s*$")
TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
ORDERED_ITEM_RE = re.compile(r"^\s*\d+\.\s+\S")
BULLET_ITEM_RE = re.compile(r"^\s*[-*]\s+\S")
```

- [ ] **Step 4: Add the helper functions**

In `scripts/audit_docs_model.py`, add right after `load_canonical_sections` (currently ends around line 157):

```python
def normalize_section_title(raw_title: str) -> str:
    title = TRAILING_PAREN_RE.sub("", raw_title).strip()
    title = re.sub(r"\s+", " ", title)
    return normalize_text(title)


def feature_section_titles(text: str) -> list[tuple[str, str]]:
    """Return (normalized, original) for each level-2 heading, deduped, in order."""

    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = SECTION_HEADING_RE.match(line)
        if not match:
            continue
        original = match.group(1).strip()
        normalized = normalize_section_title(original)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append((normalized, original))
    return result


def iter_level2_sections(text: str) -> list[list[str]]:
    """Split text into level-2 sections; lines before the first heading are dropped."""

    sections: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if SECTION_HEADING_RE.match(line):
            if current is not None:
                sections.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        sections.append(current)
    return sections
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_language_agnostic.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_language_agnostic.py
git commit -m "feat: add section-title and level-2 section helpers"
```

---

## Task 2: Reference-based feature-section consistency

Replace the fixed English seven-section check with inference from the project's own feature READMEs.

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_language_agnostic.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_language_agnostic.py`:

```python
def _write_feature(repo, name, sections):
    d = repo / "docs" / "features" / name
    d.mkdir(parents=True)
    body = "\n\n".join(f"## {s}\ncontent" for s in sections) + "\n"
    (d / "README.md").write_text(body, encoding="utf-8")


def test_consistency_passes_when_all_features_match_ptbr(tmp_path):
    secs = ["Visão Geral", "Requisitos (REQ-*)", "Critérios de Aceite (AC-*)"]
    _write_feature(tmp_path, "alpha", secs)
    _write_feature(tmp_path, "beta", secs)
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_consistency_flags_feature_missing_reference_section(tmp_path):
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "FEATURE_SECTION_INCONSISTENT"
    assert f.path == "docs/features/beta/README.md"
    assert "Questões em Aberto" in f.message


def test_consistency_single_feature_no_finding(tmp_path):
    _write_feature(tmp_path, "alpha", ["Overview", "Requirements"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []


def test_compute_feature_section_gaps_returns_original_titles(tmp_path):
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/beta/README.md": ["Dependências"]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "consistency or gaps"`
Expected: FAIL with `AttributeError: ... has no attribute 'check_feature_section_consistency'`.

- [ ] **Step 3: Add the gap computation and check functions**

In `scripts/audit_docs_model.py`, add right after `iter_level2_sections`:

```python
def compute_feature_section_gaps(repo: Path) -> dict[str, list[str]]:
    """Map each feature README (rel path) to the reference sections it is missing.

    The reference is the feature README with the most distinct level-2 sections;
    ties break toward the alphabetically first feature directory. Returns {} when
    there are fewer than two feature READMEs.
    """

    readmes: list[tuple[str, set[str], dict[str, str]]] = []
    for feature_dir in collect_feature_dirs(repo):
        readme = feature_dir / "README.md"
        if not readme.exists():
            continue
        titles = feature_section_titles(readme.read_text(encoding="utf-8"))
        normalized_set = {normalized for normalized, _ in titles}
        original_by_normalized = {normalized: original for normalized, original in titles}
        rel = str(readme.relative_to(repo))
        readmes.append((rel, normalized_set, original_by_normalized))

    if len(readmes) < 2:
        return {}

    reference_rel, _, reference_titles = max(readmes, key=lambda item: len(item[1]))

    gaps: dict[str, list[str]] = {}
    for rel, normalized_set, _ in readmes:
        if rel == reference_rel:
            continue
        missing = [
            original
            for normalized, original in reference_titles.items()
            if normalized not in normalized_set
        ]
        if missing:
            gaps[rel] = missing
    return gaps


def check_feature_section_consistency(repo: Path, findings: list[Finding]) -> None:
    for rel, missing in compute_feature_section_gaps(repo).items():
        make_finding(
            findings,
            "BLOCKER",
            "FEATURE_SECTION_INCONSISTENT",
            rel,
            "Feature README missing sections established by the reference feature: "
            + ", ".join(missing),
        )
```

- [ ] **Step 4: Remove the old fixed-heading check from check_feature_readme**

In `scripts/audit_docs_model.py`, in `check_feature_readme`, delete the now-obsolete section block. The current code (around lines 238-249) is:

```python
    lines = content.splitlines()
    normalized_lines = heading_lines(content)

    for heading_name, prefixes in FEATURE_README_REQUIRED_HEADINGS.items():
        if not any(any(line.startswith(prefix) for prefix in prefixes) for line in normalized_lines):
            make_finding(
                findings,
                "BLOCKER",
                "MISSING_README_SECTION",
                rel,
                f"Feature README missing section: {heading_name}",
            )
```

Replace it with (keep the `lines` assignment, which later code uses; drop `normalized_lines` and the loop):

```python
    lines = content.splitlines()
```

- [ ] **Step 5: Remove the now-dead constant and helper**

In `scripts/audit_docs_model.py`:
- Delete the `FEATURE_README_REQUIRED_HEADINGS = { ... }` dictionary (currently lines 68-76).
- Delete the `heading_lines` function (currently around lines 231-232):

```python
def heading_lines(text: str) -> list[str]:
    return [normalize_text(line.strip()) for line in text.splitlines() if line.strip()]
```

- [ ] **Step 6: Wire the consistency check into audit_repository**

In `scripts/audit_docs_model.py`, in `audit_repository`, after the feature loop and before `nfr_file = ...` (currently around line 661), add:

```python
    check_feature_section_consistency(repo, findings)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "consistency or gaps"`
Expected: PASS (4 tests).

- [ ] **Step 8: Run the full suite to catch breakage from removals**

Run: `python3 -m pytest tests/ -v`
Expected: any failures should ONLY be in tests that asserted the removed `MISSING_README_SECTION` behavior. If `tests/test_ai_instruction_audit.py` or `tests/test_ai_instruction_plan.py` fail, that is expected and handled in Tasks 3-4. There should be no failures referencing `MISSING_README_SECTION` (no existing test asserts it). Confirm the new file and the audit helper tests pass.

- [ ] **Step 9: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_language_agnostic.py
git commit -m "feat: reference-based feature-section consistency"
```

---

## Task 3: Structural detection for AI-instruction files

Replace English-heading matching and divergence with shape detection.

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_language_agnostic.py`, `tests/test_ai_instruction_audit.py`

- [ ] **Step 1: Write the failing tests (new structural tests)**

Append to `tests/test_language_agnostic.py`:

```python
WORKFLOW_PT = "## Workflow: nova feature\n1. Brainstorm\n2. Spec\n3. Plano\n"
PRINCIPLES_PT = "## Princípios de trabalho\n- Esclarecer\n- Pragmatismo\n- Rastreabilidade\n"


def test_detect_shapes_true_for_ptbr_file():
    text = WORKFLOW_PT + "\n" + PRINCIPLES_PT
    assert adm.detect_ai_instruction_shapes(text) == (True, True)


def test_detect_shapes_requires_distinct_sections():
    # one section has both an ordered list and bullets; the other is plain prose
    text = "## Tudo junto\n1. a\n2. b\n3. c\n- x\n- y\n- z\n## Outra\nprosa\n"
    assert adm.detect_ai_instruction_shapes(text) == (True, False)


def test_check_ai_ptbr_file_passes(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT + "\n" + PRINCIPLES_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    assert [f for f in findings if f.path == "CLAUDE.md"] == []


def test_check_ai_missing_principles_is_blocker(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert blockers[0].severity == "BLOCKER"


def test_check_ai_absent_is_info(tmp_path):
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = {(f.path, f.code, f.severity) for f in findings}
    assert ("CLAUDE.md", "AI_INSTRUCTION_FILE_ABSENT", "INFO") in codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "shapes or check_ai"`
Expected: FAIL with `AttributeError: ... has no attribute 'detect_ai_instruction_shapes'`.

- [ ] **Step 3: Add the shape detector**

In `scripts/audit_docs_model.py`, add right before `check_ai_instruction_files`:

```python
def detect_ai_instruction_shapes(text: str) -> tuple[bool, bool]:
    """Detect (has_workflow, has_principles) by structure, independent of language.

    Workflow = a level-2 section with >=3 ordered-list items.
    Principles = a *different* level-2 section with >=3 bullet items.
    """

    sections = iter_level2_sections(text)
    ordered_indexes = [
        index
        for index, section in enumerate(sections)
        if sum(1 for line in section if ORDERED_ITEM_RE.match(line)) >= 3
    ]
    bullet_indexes = [
        index
        for index, section in enumerate(sections)
        if sum(1 for line in section if BULLET_ITEM_RE.match(line)) >= 3
    ]

    workflow_index = ordered_indexes[0] if ordered_indexes else None
    principles_index = next(
        (index for index in bullet_indexes if index != workflow_index), None
    )
    return workflow_index is not None, principles_index is not None
```

- [ ] **Step 4: Rewrite check_ai_instruction_files**

In `scripts/audit_docs_model.py`, replace the entire `check_ai_instruction_files` function (currently lines 585-620) with:

```python
def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
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

        has_workflow, has_principles = detect_ai_instruction_shapes(
            path.read_text(encoding="utf-8")
        )
        if not has_workflow:
            make_finding(
                findings,
                "BLOCKER",
                "AI_INSTRUCTION_SECTION_MISSING",
                rel,
                "AI instruction file missing a workflow section "
                "(a heading followed by a numbered list of steps).",
            )
        if not has_principles:
            make_finding(
                findings,
                "BLOCKER",
                "AI_INSTRUCTION_SECTION_MISSING",
                rel,
                "AI instruction file missing a principles section "
                "(a heading followed by a bulleted list).",
            )
```

- [ ] **Step 5: Update the obsolete tests in test_ai_instruction_audit.py**

In `tests/test_ai_instruction_audit.py`:

Replace the body of `test_missing_section_is_blocker` with the structural version. The current test is:

```python
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
```

Replace with:

```python
def test_missing_section_is_blocker(tmp_path):
    sections = adm.load_canonical_sections()
    only_first = sections["## Workflow: New Feature"]
    (tmp_path / "CLAUDE.md").write_text(only_first + "\n", encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    blockers = [f for f in findings if f.path == "CLAUDE.md" and f.severity == "BLOCKER"]
    assert len(blockers) == 1
    assert blockers[0].code == "AI_INSTRUCTION_SECTION_MISSING"
    assert "principles" in blockers[0].message.lower()
```

Delete the entire `test_divergent_section_is_blocker` test (the divergence check no longer exists):

```python
def test_divergent_section_is_blocker(tmp_path):
    sections = adm.load_canonical_sections()
    tampered = sections["## Working Principles"].replace("Pragmatism", "Pragmatism CHANGED")
    text = sections["## Workflow: New Feature"] + "\n\n" + tampered + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    findings = []
    adm.check_ai_instruction_files(tmp_path, findings)
    codes = _codes_for(findings, "CLAUDE.md")
    assert codes == {"AI_INSTRUCTION_SECTION_DIVERGENT"}
```

Note: `test_identical_file_produces_no_finding` and `test_copilot_nested_path_detected` remain valid — the canonical EN file still has a numbered workflow and bulleted principles (passes), and a `# x`-only file still has neither shape (one or two `AI_INSTRUCTION_SECTION_MISSING`, set equality holds).

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_language_agnostic.py tests/test_ai_instruction_audit.py -v`
Expected: PASS (all). No reference to `AI_INSTRUCTION_SECTION_DIVERGENT` remains.

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_language_agnostic.py tests/test_ai_instruction_audit.py
git commit -m "feat: structural AI-instruction detection, drop divergence check"
```

---

## Task 4: Plan diffs for missing feature and AI sections

**Files:**
- Modify: `scripts/build_docs_alignment_plan.py`
- Test: `tests/test_language_agnostic.py`, `tests/test_ai_instruction_plan.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_language_agnostic.py`:

```python
import build_docs_alignment_plan as plan


def test_feature_section_append_diff_proposes_missing_headings(tmp_path):
    d = tmp_path / "docs" / "features" / "beta"
    d.mkdir(parents=True)
    (d / "README.md").write_text("## Visão Geral\nx\n", encoding="utf-8")
    diff = plan.feature_section_append_diff(
        tmp_path, "docs/features/beta/README.md", ["Dependências", "Questões em Aberto"]
    )
    assert "+## Dependências" in diff
    assert "+## Questões em Aberto" in diff


def test_ai_update_diff_appends_missing_principles(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(WORKFLOW_PT, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "+## Working Principles" in diff
    assert "Working Principles" not in WORKFLOW_PT  # guard: came from canonical, not the file


def test_ai_update_diff_identical_reports_no_changes(tmp_path):
    sections = adm.load_canonical_sections()
    text = sections["## Workflow: New Feature"] + "\n\n" + sections["## Working Principles"] + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    assert plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md") == "No changes required."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "append_diff or ai_update"`
Expected: FAIL with `AttributeError: ... has no attribute 'feature_section_append_diff'`.

- [ ] **Step 3: Add the append-diff helpers**

In `scripts/build_docs_alignment_plan.py`, add after `placeholder_update_diff` (and before the existing `_section_diff_block`):

```python
def _append_block_diff(target_rel: str, file_lines: list[str], block_text: str, label: str | None = None) -> str:
    added: list[str] = [""]
    if label:
        added.append(label)
    added.extend(block_text.splitlines())
    start = len(file_lines)
    header = f"@@ -{start},0 +{start + 1},{len(added)} @@"
    body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
    body.extend(f"+{line}" for line in added)
    return "\n".join(body)


def feature_section_append_diff(repo: Path, target_rel: str, missing_titles: list[str]) -> str:
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    file_lines = text.splitlines()
    added: list[str] = []
    for title in missing_titles:
        added.extend(["", f"## {title}", ""])
    start = len(file_lines)
    header = f"@@ -{start},0 +{start + 1},{len(added)} @@"
    body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
    body.extend(f"+{line}" for line in added)
    return "\n".join(body)
```

- [ ] **Step 4: Rewrite ai_instruction_update_diff**

In `scripts/build_docs_alignment_plan.py`, replace the entire `ai_instruction_update_diff` function with:

```python
def ai_instruction_update_diff(repo: Path, target_rel: str) -> str:
    # Proposes the English canonical block as a labeled starting point for any
    # structurally-missing section. Human-facing; not intended for `git apply`.
    canonical = adm.load_canonical_sections()
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    file_lines = text.splitlines()
    has_workflow, has_principles = adm.detect_ai_instruction_shapes(text)

    label = (
        "<!-- plan-docs-standardization: English starting point — "
        "translate to your project's language -->"
    )
    blocks: list[str] = []
    if not has_workflow:
        blocks.append(_append_block_diff(target_rel, file_lines, canonical["## Workflow: New Feature"], label))
    if not has_principles:
        blocks.append(_append_block_diff(target_rel, file_lines, canonical["## Working Principles"], label))

    return "\n\n".join(blocks) if blocks else "No changes required."
```

- [ ] **Step 5: Remove the dead _section_diff_block**

In `scripts/build_docs_alignment_plan.py`, delete the entire `_section_diff_block` function (no longer referenced after Step 4).

- [ ] **Step 6: Route feature-section gaps in proposed_diffs**

In `scripts/build_docs_alignment_plan.py`, in `proposed_diffs`, just before the `for target_rel in alter_files:` loop, add:

```python
    feature_gaps = adm.compute_feature_section_gaps(repo)
```

Then, inside that loop, the current AI-instruction branch is:

```python
        if target_rel in AI_INSTRUCTION_FILES:
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": ai_instruction_update_diff(repo, target_rel),
                }
            )
            continue
```

Immediately after that branch (still inside the loop, before the `reasons = ...` line), add:

```python
        if target_rel in feature_gaps:
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": feature_section_append_diff(repo, target_rel, feature_gaps[target_rel]),
                }
            )
            continue
```

- [ ] **Step 7: Remove the obsolete divergence test in test_ai_instruction_plan.py**

In `tests/test_ai_instruction_plan.py`, delete the entire `test_ai_instruction_update_diff_replaces_divergent_section` test:

```python
def test_ai_instruction_update_diff_replaces_divergent_section(tmp_path):
    sections = adm.load_canonical_sections()
    tampered = sections["## Working Principles"].replace("Pragmatism", "Pragmatism CHANGED")
    text = sections["## Workflow: New Feature"] + "\n\n" + tampered + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "-- **Pragmatism CHANGED**" in diff or "-- **Pragmatism CHANGED**: " in diff
    assert "+- **Pragmatism**" in diff
```

The remaining tests in that file stay valid: `test_ai_instruction_update_diff_appends_missing_section` (workflow-only file → principles appended; still true), `test_ai_instruction_update_diff_identical_file_reports_no_changes` (both shapes present → "No changes required."), plus the `collect_actions` and absent-note tests.

- [ ] **Step 8: Run tests to verify they pass**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all). No reference to `_section_diff_block` or the divergence behavior remains.

- [ ] **Step 9: Commit**

```bash
git add scripts/build_docs_alignment_plan.py tests/test_language_agnostic.py tests/test_ai_instruction_plan.py
git commit -m "feat: propose reference headings and structural AI starting points"
```

---

## Task 5: Update references, SKILL.md, README.md

**Files:**
- Modify: `references/compliance-rules.md`, `references/docs-model-spec.md`, `SKILL.md`, `README.md`

Read each file first to anchor exact wording; the edits below specify the target content.

- [ ] **Step 1: Rewrite R003 and R010, remove R011 in compliance-rules.md**

In `references/compliance-rules.md`:

Replace the `### R003 Feature README minimum sections (BLOCKER)` block with:

```markdown
### R003 Feature README section consistency (BLOCKER)

In alignment mode, the expected section set is inferred from the project's own feature
READMEs: the reference is the feature README with the most distinct level-2 sections
(ties break toward the alphabetically first feature). Every other feature README must
contain the same section set (compared by normalized heading text — trimmed, lowercased,
accent- and trailing-parenthetical-stripped). A README missing a reference section is
non-compliant (`FEATURE_SECTION_INCONSISTENT`). With fewer than two feature READMEs, no
consistency check runs. The skill never compares against fixed English headings.
```

Replace the `### R010 AI instruction section missing (BLOCKER)` block with:

```markdown
### R010 AI instruction section missing (BLOCKER)

For each existing AI instruction file, two sections are detected structurally (language
independent): a workflow section (a heading followed by a numbered list of >=3 steps) and
a principles section (a different heading followed by a bulleted list of >=3 items). A
file missing either shape is non-compliant (`AI_INSTRUCTION_SECTION_MISSING`).
```

Delete the entire `### R011 AI instruction section divergent (BLOCKER)` block.

- [ ] **Step 2: Reword docs-model-spec.md**

In `references/docs-model-spec.md`:

Under `## Feature README Minimum Sections`, replace its body (the bulleted list of the seven English sections) with:

```markdown
The seven canonical sections (Overview, Requirements, Acceptance Criteria, Dependencies,
Traceability, Out of Scope, Open Questions) are the English baseline used by bootstrap
templates. In alignment mode the skill does not enforce these English names. Instead it
infers the expected section set from the project's own feature READMEs (the most complete
feature is the reference) and requires the other features to be consistent with it, in
whatever language the project documents.
```

In the `## AI Instruction Files (optional, never created)` section, replace the final paragraph (the one beginning "For an existing file:") with:

```markdown
For an existing file, the skill detects two sections structurally, independent of
language: a workflow section (heading + numbered step list) and a principles section
(heading + bulleted list). A file missing either shape is a `BLOCKER`; an absent file is
`INFO`. Content is not compared against the English block, so localized guidelines pass.
```

- [ ] **Step 3: Update SKILL.md**

In `SKILL.md`, in the `## AI Instruction Files Alignment` section, replace the two bullets about missing/divergent sections with:

```markdown
- If a file exists, the skill detects a workflow section (numbered steps) and a principles
  section (bulleted list) structurally, independent of language. Missing either is a
  `BLOCKER`; the proposed diff appends the English canonical block as a starting point to
  translate. Never apply changes.
```

In `SKILL.md`, in the `Apply these defaults:` list, add a bullet:

```markdown
- Alignment is language-agnostic: feature-section expectations are inferred from the project's own docs, and AI-instruction sections are detected structurally; bundled templates and bootstrap stay English
```

- [ ] **Step 4: Update README.md**

In `README.md`, in the `## AI instruction files alignment` section, replace the second bullet of "Behavior:" (the one about missing/divergent → BLOCKER) with:

```markdown
- For an existing file, the skill detects a workflow section (numbered steps) and a
  principles section (bulleted list) by structure, independent of language. Missing either
  is a BLOCKER; the proposed diff (never applied) appends the English canonical block as a
  starting point to translate.
```

In `README.md`, under `### Traceability rules` or near the canonical-model description, add a short note:

```markdown
> **Language:** Bundled templates are English and bootstrap scaffolds English. In
> alignment mode the skill is language-agnostic — it infers feature-section expectations
> from the project's own docs and detects AI-instruction sections structurally, so docs in
> any language pass without false blockers.
```

- [ ] **Step 5: Verify the docs are consistent**

Run: `grep -n "FEATURE_SECTION_INCONSISTENT\|structurally\|language-agnostic\|R011" references/compliance-rules.md references/docs-model-spec.md SKILL.md README.md`
Expected: matches for the new content in references/SKILL/README; NO match for `R011` (it was removed).

- [ ] **Step 6: Commit**

```bash
git add references/compliance-rules.md references/docs-model-spec.md SKILL.md README.md
git commit -m "docs: document language-agnostic compliance"
```

---

## Task 6: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 2: Simulate a consistent pt-BR project and confirm zero false blockers from sections**

Run:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/docs/nfr" "$TMP/docs/features/login" "$TMP/docs/features/perfil" "$TMP/docs/reports"
# minimal required root files so we isolate section findings
for f in index PROJECT_BRIEF ARCHITECTURE GLOSSARY DECISIONS ROADMAP BACKLOG; do echo "# $f" > "$TMP/docs/$f.md"; done
echo "# nfr" > "$TMP/docs/nfr/NON_FUNCTIONAL.md"; echo "# idx" > "$TMP/docs/features/INDEX.md"; echo "# rep" > "$TMP/docs/reports/README.md"
echo "# reqs" > "$TMP/docs/requirements-mkdocs.txt"; printf 'site_name: x\nnav:\n  - Home: index.md\n' > "$TMP/mkdocs.yml"
for feat in login perfil; do
  printf '## Visão Geral\nx\n\n## Requisitos (REQ-*)\n`REQ-%s-001`\n\n## Critérios de Aceite (AC-*)\n### AC-%s-001 - t (REQ-%s-001)\n' "${feat^^}" "${feat^^}" "${feat^^}" > "$TMP/docs/features/$feat/README.md"
  for x in flows rules notes; do echo "# $x" > "$TMP/docs/features/$feat/$x.md"; done
done
printf '## Workflow: nova feature\n1. a\n2. b\n3. c\n\n## Princípios\n- x\n- y\n- z\n' > "$TMP/CLAUDE.md"
echo "=== AI/feature-section findings (expect none) ==="
python3 scripts/audit_docs_model.py "$TMP" --format json | python3 -c "import sys,json;d=json.load(sys.stdin);print([f['code'] for f in d['findings'] if f['code'] in ('FEATURE_SECTION_INCONSISTENT','AI_INSTRUCTION_SECTION_MISSING')])"
rm -rf "$TMP"
```

Expected: `[]` — the pt-BR docs produce no section/AI false blockers.

- [ ] **Step 3: Confirm a genuinely inconsistent feature is still flagged**

Run:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/docs/features/alpha" "$TMP/docs/features/beta"
printf '## Visão Geral\nx\n## Requisitos\nr\n## Questões em Aberto\nq\n' > "$TMP/docs/features/alpha/README.md"
printf '## Visão Geral\nx\n## Requisitos\nr\n' > "$TMP/docs/features/beta/README.md"
python3 scripts/audit_docs_model.py "$TMP" --format json | python3 -c "import sys,json;d=json.load(sys.stdin);print([(f['path'],f['code']) for f in d['findings'] if f['code']=='FEATURE_SECTION_INCONSISTENT'])"
rm -rf "$TMP"
```

Expected: one `FEATURE_SECTION_INCONSISTENT` for `docs/features/beta/README.md`.

- [ ] **Step 4: Confirm the five-section output contract still holds**

Run: `python3 scripts/build_docs_alignment_plan.py . | grep -E "^## (Executive Summary|Compliance Matrix|Immediate Alignment Plan|File Create/Alter List|Proposed Diffs)"`
Expected: all five canonical sections present.
