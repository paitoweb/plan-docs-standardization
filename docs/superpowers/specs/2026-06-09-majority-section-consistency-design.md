# Design: Majority-Based Feature-Section Consistency

- Date: 2026-06-09
- Status: Approved (design)
- Skill: `plan-docs-standardization`

## Problem

The current feature-section consistency check (added in the language-agnostic work)
picks the feature README with the most distinct level-2 sections as the reference and
requires every other feature README to contain that reference's full section set.

Real-world testing exposed a fragile, non-obvious effect: adding a single new section to
ONE richer, more detailed feature turns every other feature into a `BLOCKER`. A single
legitimate feature (e.g., `document-generation`) produced a cascade of ~12 alerts. The
rule effectively forces either "level every feature up" or "never let one feature be more
detailed than the others."

## Goal

Replace reference-based consistency with majority-based consistency, and downgrade the
finding to `WARN`. A section is only expected when most features already use it, so a
unique section on one feature no longer cascades onto the others; and because the rule is
an inferred convention rather than a canonical requirement, it warns rather than blocks.

## Behavior

In `compute_feature_section_gaps(repo)`:

- For each feature README that exists, compute its set of normalized level-2 section
  titles (via `feature_section_titles`, which already dedupes per file).
- Count, across feature READMEs, how many contain each normalized title (one count per
  feature).
- The **expected set** is every normalized title whose count is a **strict majority** of
  the feature READMEs: `count > readme_count / 2`.
- For each feature README, the gap is the expected titles it lacks; report the original
  (project-language) display text.
- With fewer than two feature READMEs, return `{}` (no convention to infer).

There is no longer a "reference" feature; the `max(...)` selection and the alphabetical
tie-break (and its test) are removed.

### Threshold semantics (strict majority)

- A section in only 1 of N features is never expected (`1 > N/2` is false for N >= 2), so
  one-off sections do not cascade.
- 2 features: a section must be in both to be expected (`count > 1.0` => `count >= 2`).
- 3 features: a section in 2 of 3 is expected (`2 > 1.5`); the one missing it is flagged.
- 12 features: a section must be in 7+ to be expected.

### Display text determinism

For each expected normalized title, the original display text used in messages and diffs
is the original heading from the first feature (in alphabetical feature-directory order)
that contains it.

## Severity

`check_feature_section_consistency` emits the finding at `WARN` severity (was `BLOCKER`).
The code remains `FEATURE_SECTION_INCONSISTENT`. The message is reworded to reference the
majority of features, e.g.: "Feature README missing sections used by the majority of
features: <titles>".

## Plan / Diff

`build_docs_alignment_plan.py` is unchanged in routing: `collect_actions` routes by code
(not severity), so a `FEATURE_SECTION_INCONSISTENT` finding still lands in the alter list
and `feature_section_append_diff` still proposes appending the majority section headings.
A `WARN` finding producing a proposed (non-applied) diff is consistent with the skill's
existing behavior.

## Components / Files

- `scripts/audit_docs_model.py`:
  - Rewrite `compute_feature_section_gaps` to majority-based logic; remove the reference
    selection and the tie-break comment.
  - Change `check_feature_section_consistency` severity to `WARN` and reword the message.
- `references/compliance-rules.md`:
  - Rewrite `R003` to describe majority-based consistency and `WARN` severity.
  - Adjust the classification rule that currently states a missing required section is a
    `BLOCKER`, so it does not contradict the new `WARN` feature-section rule.
- `references/docs-model-spec.md`:
  - Update the `Feature README Minimum Sections` wording: the expected set is inferred
    from the majority of the project's feature READMEs (not the most-complete reference).
- `SKILL.md`, `README.md`:
  - Update any wording implying reference-based or blocking feature-section checks.
- Tests (`tests/test_language_agnostic.py`):
  - Remove the reference/tie-break tests.
  - Add majority tests: 3 features where 2 share a section and 1 lacks it → that one is
    flagged (`WARN`); a section unique to 1 of 3 → no finding; all-consistent → no
    finding; single feature → no finding.
  - Update `test_compute_feature_section_gaps_returns_original_titles` to a 3-feature
    majority scenario.
  - Update any assertion expecting `BLOCKER` for this code to expect `WARN`.

## Severity Map (after change)

| Scenario | Code | Severity |
|---|---|---|
| Feature README missing a majority section | `FEATURE_SECTION_INCONSISTENT` | WARN |
| AI instruction file: workflow/principles shape missing | `AI_INSTRUCTION_SECTION_MISSING` | BLOCKER |
| AI instruction file absent | `AI_INSTRUCTION_FILE_ABSENT` | INFO |

## Out of Scope

- Configurable thresholds (strict majority is the fixed rule).
- Flagging the outlier feature that introduced a unique section.
- Any change to AI-instruction detection or other checks.

## Open Questions

None.
