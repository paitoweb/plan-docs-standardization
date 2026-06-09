# Canonical Documentation Model

## Purpose

Define the strict baseline documentation model that this skill enforces for bootstrap and alignment planning.

## Canonical Required Files

### Root-level required files

- `mkdocs.yml`
- `docs/requirements-mkdocs.txt`
- `docs/index.md`
- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/GLOSSARY.md`
- `docs/DECISIONS.md`
- `docs/ROADMAP.md`
- `docs/BACKLOG.md`
- `docs/nfr/NON_FUNCTIONAL.md`
- `docs/features/INDEX.md`
- `docs/reports/README.md`

### Traceability configuration (Cursor / full Docs-First)

- `docs/traceability.json` — maps each feature to `source_globs`, `test_globs`, and `exclude_globs`

When `.cursor/` exists and mode is `alignment`, missing `docs/traceability.json` is a `BLOCKER`.
Source files must cite `REQ-*` IDs; test files must include `Traceability:` comments.

### Feature-level required files

For each directory under `docs/features/<feature>/`:

- `README.md`
- `flows.md`
- `rules.md`
- `notes.md`

## Feature README Minimum Sections

The seven canonical sections (Overview, Requirements, Acceptance Criteria, Dependencies,
Traceability, Out of Scope, Open Questions) are the English baseline used by bootstrap
templates. In alignment mode the skill does not enforce these English names. Instead it
infers the expected section set from the project's own feature READMEs by strict majority
(a section is expected when more than half of the features use it) and warns when a
feature is missing an expected section, in whatever language the project documents. A
section unique to one richer feature is not required of the others.

## ID Conventions

- Functional requirement: `REQ-<FEATURE>-NNN`
- Acceptance criterion: `AC-<FEATURE>-NNN`
- Non-functional requirement: `NFR-NNN`
- Non-functional acceptance criterion: `AC-NFR-NNN`

Where:

- `<FEATURE>` uses uppercase letters, digits, and `-`
- `NNN` is zero-padded, three digits

## Traceability Rules

- Every AC heading in feature README must reference at least one `REQ-*` in the same file.
- Every AC-NFR heading in `docs/nfr/NON_FUNCTIONAL.md` must reference at least one `NFR-*` in the same file.
- Internal markdown links must resolve to existing files.
- `mkdocs.yml` nav markdown references must resolve to existing files under `docs/`.

## Non-canonical Artifacts To Ignore

- `.DS_Store`
- `.obsidian/`
- editor-specific metadata
- OS cache files

## AI Instruction Files (optional, never created)

The skill optionally aligns AI instruction files when they already exist. It never
creates them.

Target files (repository root, plus the GitHub path):

- `CLAUDE.md`
- `AGENTS.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`

When the repository uses Cursor (`.cursor/` directory exists), also audit:

- `.cursor/rules/docs-first-workflow.mdc`

Canonical guidelines block (single source of truth, English only):

- `assets/templates/ai-instructions/guidelines.en.md`

It defines two sections, located by title:

- `## Workflow: New Feature`
- `## Working Principles`

For an existing file, the skill detects two sections structurally, independent of
language: a workflow section (heading + numbered step list) and a principles section
(heading + bulleted list). A file missing either shape is a `BLOCKER`; an absent file is
`INFO`. Content is not compared against the English block, so localized guidelines pass.

## Output Contract

The planning output must always include:

1. `Executive Summary`
2. `Compliance Matrix (BLOCKER/WARN/INFO)`
3. `Immediate Alignment Plan`
4. `File Create/Alter List`
5. `Proposed Diffs (not applied)`

## Severity Guidelines

- `BLOCKER`: required structure/rule not satisfied.
- `WARN`: non-blocking quality issue.
- `INFO`: contextual guidance.
