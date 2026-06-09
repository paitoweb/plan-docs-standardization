# Design: Language-Agnostic Compliance

- Date: 2026-06-09
- Status: Approved (design)
- Skill: `plan-docs-standardization`

## Problem

The canonical model hardcodes English section headings. The feature-README check
(`R003`) matches the seven required sections by English text (`## Overview`,
`## Requirements`, …), and the AI-instruction check matches the two sections by exact
English headings (`## Workflow: New Feature`, `## Working Principles`) plus a divergence
comparison against the English canonical block.

When run against a project that deliberately documents in another language (e.g.,
pt-BR: `## Visão Geral`, `## Requisitos`, `## Workflow: nova feature`), this produces
large numbers of false `BLOCKER`s (~91 from feature sections + 2 from AI-instruction
sections in the reported case). The documentation is legitimate; the model is simply
too rigid about language.

## Goal

Make alignment-mode compliance language-agnostic by inferring expectations from the
project's own documentation, never comparing against fixed English text. The skill and
its bundled templates remain authored in English; bootstrap (no docs) still scaffolds in
English.

## Principles

- The skill never needs to identify the language (it does not detect "this is pt-BR").
  It adopts the headings the project already uses.
- Bundled templates stay English. Bootstrap mode (no `docs/`) scaffolds English; there is
  nothing to infer from.
- Language-neutral checks are unchanged: ID formats (`REQ-*`/`AC-*`/`NFR-*`/`AC-NFR-*`),
  presence of REQ/AC IDs, AC→REQ and AC-NFR→NFR traceability, internal links, and
  `mkdocs.yml` nav.
- Root docs (`PROJECT_BRIEF.md`, `ARCHITECTURE.md`, …) have no section-name checks today
  and stay that way — already language-agnostic.

## Feature README Sections (replaces R003)

Replace the fixed seven-section English check with reference-based consistency.

### Reference selection

- The reference is the feature README under `docs/features/<feature>/README.md` with the
  largest number of distinct level-2 (`##`) section headings.
- Tie-break: the alphabetically first feature directory name.

### Expected section set

- The expected set is the reference's `##` headings, each normalized by:
  - trimming and collapsing internal whitespace,
  - lowercasing,
  - stripping accents (reuse the existing `normalize_text`),
  - removing a single trailing parenthetical annotation, e.g. `(REQ-*)` / `(AC-*)`.

### Rule

- Every other feature README must contain every heading in the expected set (compared by
  the same normalization). A README missing one or more is non-compliant.
- Finding: `FEATURE_SECTION_INCONSISTENT` (`BLOCKER`). Message names the missing
  heading(s) and notes they come from the reference feature.
- If there are 0 or 1 feature directories, no consistency check runs (there is no
  established convention to compare against). ID/traceability checks still run.

### Removed

- The hardcoded `FEATURE_README_REQUIRED_HEADINGS` dictionary and the
  `MISSING_README_SECTION` finding it produced.

### Trade-off (accepted)

Using the most complete feature as the reference means a section unique to that one
feature becomes required of all others. This is the chosen behavior.

## AI Instruction Files (replaces English-text section + divergence checks)

Target files unchanged: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`.

- Absent file → `INFO` `AI_INSTRUCTION_FILE_ABSENT` (unchanged; skill never creates).
- Existing file → detect two sections by structural signal, independent of heading text:
  - **Workflow-shaped**: a `##` section whose body contains an ordered list of at least
    three items (lines matching `^\s*\d+\.\s`).
  - **Principles-shaped**: a *different* `##` section whose body contains a bullet list of
    at least three items (lines matching `^\s*[-*]\s`).
- Missing either shape → `BLOCKER` `AI_INSTRUCTION_SECTION_MISSING` (now structural).
- `AI_INSTRUCTION_SECTION_DIVERGENT` is **removed** — translated content cannot be
  validated against the English canonical block.
- The English canonical block `assets/templates/ai-instructions/guidelines.en.md` is
  retained as a starting-point suggestion used in diffs when a section is missing.

### Disambiguation

If a single `##` section satisfies both signals (numbered list and bullets), it counts
toward whichever shape is not yet satisfied by another section, preferring to assign it
as the workflow section. Two distinct sections are required for both shapes to be
considered present.

## Diffs and Bootstrap

- Alignment, feature README missing a section → propose a diff that adds the reference's
  heading text (in the project's language); body content is left to the author (no
  placeholder-only content emitted).
- Alignment, AI-instruction file missing a section → propose a diff that appends the
  English canonical block as a starting point, labeled to be translated to the project's
  language.
- Bootstrap (no `docs/`) → English templates, unchanged.

## Severity Map

| Scenario | Code | Severity |
|---|---|---|
| Feature README missing a reference section | `FEATURE_SECTION_INCONSISTENT` | BLOCKER |
| AI instruction file: workflow or principles shape missing | `AI_INSTRUCTION_SECTION_MISSING` | BLOCKER |
| AI instruction file absent | `AI_INSTRUCTION_FILE_ABSENT` | INFO |

## Components / Files

- `scripts/audit_docs_model.py`:
  - Remove `FEATURE_README_REQUIRED_HEADINGS` and its check.
  - Add reference selection + expected-set inference + per-feature consistency check.
  - Replace AI-instruction heading-text matching and divergence with structural
    detection (`section_span` reused; new ordered-list / bullet-list detectors).
  - Remove `AI_INSTRUCTION_SECTION_DIVERGENT`; drop the
    `AI_INSTRUCTION_SECTION_HEADINGS` constant usage for matching (keep canonical block
    loading for diff suggestions only).
- `scripts/build_docs_alignment_plan.py`:
  - Feature-section alters: propose the reference heading text.
  - AI-instruction alters: keep proposing the English canonical block as a labeled
    starting point; drop divergence-driven replace.
- `references/compliance-rules.md`: rewrite R003 (reference-based consistency),
  rewrite R010 (structural AI detection), remove R011.
- `references/docs-model-spec.md`: reword the feature-section and AI-instruction rules
  to describe inference; clarify bootstrap stays English.
- `SKILL.md`, `README.md`: document the language-agnostic behavior.
- Tests:
  - Feature-section consistency: a pt-BR project with consistent sections passes; a
    feature missing a reference section is `BLOCKER`; an English project still works;
    single-feature project produces no consistency finding.
  - AI-instruction structural detection: a pt-BR `CLAUDE.md` with numbered workflow +
    principle bullets passes; missing either shape is `BLOCKER`; absent → INFO.
  - Update plan tests for the new diff behavior; remove divergence tests.

## Out of Scope

- Language detection / locale identification.
- Bundled translation tables.
- Validating the content (beyond structure) of localized AI-instruction sections.
- Changing bootstrap scaffolding language (stays English).

## Open Questions

None.
