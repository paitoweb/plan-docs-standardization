# Majority-Based Feature-Section Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace reference-based feature-section consistency (which cascaded BLOCKERs from one richer feature onto all others) with strict-majority inference at WARN severity.

**Architecture:** `compute_feature_section_gaps` in `scripts/audit_docs_model.py` is rewritten to mark a section "expected" only when a strict majority (`count > n/2`) of feature READMEs use it, eliminating one-off cascades; `check_feature_section_consistency` emits WARN instead of BLOCKER. Docs and tests are updated to match.

**Tech Stack:** Python 3.12, pytest. No new dependencies.

---

## File Structure

**Modify:**
- `scripts/audit_docs_model.py` — rewrite `compute_feature_section_gaps` (majority); change `check_feature_section_consistency` severity to WARN + reword message.
- `tests/test_language_agnostic.py` — replace reference/tie-break tests with majority tests.
- `references/compliance-rules.md` — rewrite R003; fix the classification-rules bullet.
- `references/docs-model-spec.md` — reword feature-section inference (majority, not reference).
- `SKILL.md` — update the language-agnostic default bullet to mention majority/WARN.

---

## Task 1: Majority-based gaps + WARN severity

**Files:**
- Modify: `scripts/audit_docs_model.py`
- Test: `tests/test_language_agnostic.py`

- [ ] **Step 1: Update the tests to majority semantics**

In `tests/test_language_agnostic.py`, make these changes.

KEEP `test_consistency_passes_when_all_features_match_ptbr` unchanged (two features sharing all sections → each section has count 2 > 1.0 → expected → no gaps).

REPLACE the test `test_consistency_flags_feature_missing_reference_section`. Its current code is:

```python
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
```

Replace it with these two tests:

```python
def test_consistency_flags_feature_missing_majority_section(tmp_path):
    # 2 of 3 features use "Questões em Aberto" → majority → the third is flagged (WARN)
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos", "Questões em Aberto"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "FEATURE_SECTION_INCONSISTENT"
    assert f.severity == "WARN"
    assert f.path == "docs/features/gamma/README.md"
    assert "Questões em Aberto" in f.message


def test_consistency_unique_section_does_not_cascade(tmp_path):
    # one richer feature has an extra section; it must NOT be required of the others
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Métricas"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    findings = []
    adm.check_feature_section_consistency(tmp_path, findings)
    assert findings == []
```

KEEP `test_consistency_single_feature_no_finding` unchanged.

REPLACE `test_compute_feature_section_gaps_returns_original_titles`. Its current code is:

```python
def test_compute_feature_section_gaps_returns_original_titles(tmp_path):
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/beta/README.md": ["Dependências"]}
```

Replace it with:

```python
def test_compute_feature_section_gaps_returns_original_titles(tmp_path):
    # "Dependências" is in 2 of 3 features → majority → the third's gap reports it
    _write_feature(tmp_path, "alpha", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "beta", ["Visão Geral", "Requisitos", "Dependências"])
    _write_feature(tmp_path, "gamma", ["Visão Geral", "Requisitos"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/gamma/README.md": ["Dependências"]}
```

DELETE the test `test_compute_feature_section_gaps_tie_breaks_to_alphabetical_first` entirely. Its current code is:

```python
def test_compute_feature_section_gaps_tie_breaks_to_alphabetical_first(tmp_path):
    # Equal distinct-section counts; alpha must win the reference tie.
    _write_feature(tmp_path, "alpha", ["Comum", "Só Alpha"])
    _write_feature(tmp_path, "beta", ["Comum", "Só Beta"])
    gaps = adm.compute_feature_section_gaps(tmp_path)
    assert gaps == {"docs/features/beta/README.md": ["Só Alpha"]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "consistency or gaps"`
Expected: FAIL — `test_consistency_flags_feature_missing_majority_section` fails (current reference logic flags only against the most-complete feature and would emit BLOCKER, not WARN), and `test_consistency_unique_section_does_not_cascade` fails (current logic makes alpha the reference and flags beta+gamma for missing "Métricas").

- [ ] **Step 3: Rewrite compute_feature_section_gaps**

In `scripts/audit_docs_model.py`, replace the entire `compute_feature_section_gaps` function (currently lines 181-218) with:

```python
def compute_feature_section_gaps(repo: Path) -> dict[str, list[str]]:
    """Map each feature README (rel path) to the majority sections it is missing.

    A section is "expected" when a strict majority of feature READMEs use it
    (count > readme_count / 2). A section unique to one richer feature never becomes
    expected, so it does not cascade onto the others. Returns {} when there are fewer
    than two feature READMEs.
    """

    feature_sets: list[tuple[str, set[str]]] = []
    counts: dict[str, int] = {}
    first_original: dict[str, str] = {}
    for feature_dir in collect_feature_dirs(repo):
        readme = feature_dir / "README.md"
        if not readme.exists():
            continue
        titles = feature_section_titles(readme.read_text(encoding="utf-8"))
        normalized_set = {normalized for normalized, _ in titles}
        for normalized, original in titles:
            if normalized not in first_original:
                first_original[normalized] = original
        for normalized in normalized_set:
            counts[normalized] = counts.get(normalized, 0) + 1
        feature_sets.append((str(readme.relative_to(repo)), normalized_set))

    readme_count = len(feature_sets)
    if readme_count < 2:
        return {}

    expected = [
        normalized
        for normalized in first_original
        if counts[normalized] > readme_count / 2
    ]

    gaps: dict[str, list[str]] = {}
    for rel, normalized_set in feature_sets:
        missing = [first_original[n] for n in expected if n not in normalized_set]
        if missing:
            gaps[rel] = missing
    return gaps
```

- [ ] **Step 4: Change the severity and message in check_feature_section_consistency**

In `scripts/audit_docs_model.py`, replace the entire `check_feature_section_consistency` function (currently lines 221-230) with:

```python
def check_feature_section_consistency(repo: Path, findings: list[Finding]) -> None:
    for rel, missing in compute_feature_section_gaps(repo).items():
        make_finding(
            findings,
            "WARN",
            "FEATURE_SECTION_INCONSISTENT",
            rel,
            "Feature README missing sections used by the majority of features: "
            + ", ".join(missing),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_language_agnostic.py -v -k "consistency or gaps"`
Expected: PASS (5 tests: the kept pass test, the two new majority tests, single-feature, and the gaps test).

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS. (No other test asserts BLOCKER for `FEATURE_SECTION_INCONSISTENT`.)

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_docs_model.py tests/test_language_agnostic.py
git commit -m "feat: majority-based feature-section consistency at WARN"
```

---

## Task 2: Update documentation

**Files:**
- Modify: `references/compliance-rules.md`, `references/docs-model-spec.md`, `SKILL.md`

Read each file first to anchor the exact current wording.

- [ ] **Step 1: Rewrite R003 in compliance-rules.md**

In `references/compliance-rules.md`, replace the `### R003 ...` block. Its current text is:

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

Replace with:

```markdown
### R003 Feature README section consistency (WARN)

In alignment mode, the expected section set is inferred from the project's own feature
READMEs by strict majority: a section is expected when more than half of the feature
READMEs use it (compared by normalized heading text — trimmed, lowercased, accent- and
trailing-parenthetical-stripped). A feature README missing an expected section is
reported as `WARN` (`FEATURE_SECTION_INCONSISTENT`). A section unique to one richer
feature is never expected of the others, so it does not cascade. With fewer than two
feature READMEs, no consistency check runs. The skill never compares against fixed
English headings.
```

- [ ] **Step 2: Fix the classification-rules bullet in compliance-rules.md**

In `references/compliance-rules.md`, in the `## Classification Rules` list, the bullet currently reads:

```markdown
- Required section missing => `BLOCKER`
```

Replace that single bullet with these two:

```markdown
- AI instruction workflow/principles section missing => `BLOCKER`
- Feature README section missing from the majority => `WARN`
```

- [ ] **Step 3: Reword the feature-section paragraph in docs-model-spec.md**

In `references/docs-model-spec.md`, under `## Feature README Minimum Sections`, the body currently reads:

```markdown
The seven canonical sections (Overview, Requirements, Acceptance Criteria, Dependencies,
Traceability, Out of Scope, Open Questions) are the English baseline used by bootstrap
templates. In alignment mode the skill does not enforce these English names. Instead it
infers the expected section set from the project's own feature READMEs (the most complete
feature is the reference) and requires the other features to be consistent with it, in
whatever language the project documents.
```

Replace with:

```markdown
The seven canonical sections (Overview, Requirements, Acceptance Criteria, Dependencies,
Traceability, Out of Scope, Open Questions) are the English baseline used by bootstrap
templates. In alignment mode the skill does not enforce these English names. Instead it
infers the expected section set from the project's own feature READMEs by strict majority
(a section is expected when more than half of the features use it) and warns when a
feature is missing an expected section, in whatever language the project documents. A
section unique to one richer feature is not required of the others.
```

- [ ] **Step 4: Update the language-agnostic default bullet in SKILL.md**

In `SKILL.md`, in the `Apply these defaults:` list, the bullet currently reads:

```markdown
- Alignment is language-agnostic: feature-section expectations are inferred from the project's own docs, and AI-instruction sections are detected structurally; bundled templates and bootstrap stay English
```

Replace with:

```markdown
- Alignment is language-agnostic: feature-section expectations are inferred by strict majority of the project's own feature docs (`WARN`), and AI-instruction sections are detected structurally (`BLOCKER`); bundled templates and bootstrap stay English
```

- [ ] **Step 5: Verify docs consistency**

Run: `grep -rn "most complete feature\|the reference is the feature\|R003 Feature README section consistency (BLOCKER)" references/ SKILL.md README.md`
Expected: no matches (all stale reference/BLOCKER wording for R003 is gone).

Run: `grep -rn "majority" references/compliance-rules.md references/docs-model-spec.md SKILL.md`
Expected: matches in all three.

- [ ] **Step 6: Commit**

```bash
git add references/compliance-rules.md references/docs-model-spec.md SKILL.md
git commit -m "docs: majority-based feature-section consistency (WARN)"
```

---

## Task 3: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 2: Confirm no cascade from one richer feature**

Run:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/docs/features/a" "$TMP/docs/features/b" "$TMP/docs/features/rich"
for f in a b; do printf '## Visão Geral\nx\n## Requisitos\nr\n' > "$TMP/docs/features/$f/README.md"; done
printf '## Visão Geral\nx\n## Requisitos\nr\n## Métricas\nm\n## Notas Extras\nn\n' > "$TMP/docs/features/rich/README.md"
python3 scripts/audit_docs_model.py "$TMP" --format json | python3 -c "import sys,json;d=json.load(sys.stdin);print([(f['path'],f['severity']) for f in d['findings'] if f['code']=='FEATURE_SECTION_INCONSISTENT'])"
rm -rf "$TMP"
```

Expected: `[]` — the rich feature's unique sections (`Métricas`, `Notas Extras`, each in 1 of 3) are not majority, so a/b are not flagged. No cascade.

- [ ] **Step 3: Confirm a genuine majority gap is flagged as WARN**

Run:

```bash
TMP=$(mktemp -d)
mkdir -p "$TMP/docs/features/a" "$TMP/docs/features/b" "$TMP/docs/features/c"
for f in a b; do printf '## Visão Geral\nx\n## Requisitos\nr\n## Questões\nq\n' > "$TMP/docs/features/$f/README.md"; done
printf '## Visão Geral\nx\n## Requisitos\nr\n' > "$TMP/docs/features/c/README.md"
python3 scripts/audit_docs_model.py "$TMP" --format json | python3 -c "import sys,json;d=json.load(sys.stdin);print([(f['path'],f['severity'],f['code']) for f in d['findings'] if f['code']=='FEATURE_SECTION_INCONSISTENT'])"
rm -rf "$TMP"
```

Expected: exactly one entry — `('docs/features/c/README.md', 'WARN', 'FEATURE_SECTION_INCONSISTENT')` (`Questões` is in 2 of 3 → majority → c flagged, at WARN).

- [ ] **Step 4: Confirm the five-section output contract still holds**

Run: `python3 scripts/build_docs_alignment_plan.py . | grep -E "^## (Executive Summary|Compliance Matrix|Immediate Alignment Plan|File Create/Alter List|Proposed Diffs)"`
Expected: all five canonical sections present.
