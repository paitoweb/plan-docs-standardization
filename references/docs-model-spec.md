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

### Feature-level required files

For each directory under `docs/features/<feature>/`:

- `README.md`
- `flows.md`
- `rules.md`
- `notes.md`

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

## Feature Documentation Is The Spec

`docs/features/<feature>/` is the single source of truth for a feature's behavior. There is
no separate "spec" artifact in this model: the spec *is* the feature doc — versioned,
editable when behavior changes.

Design/brainstorm documents produced by tooling (canonically `docs/superpowers/specs/`) are
**outside the model**. A dated design doc records one execution's intent; once the
implementation evolves it silently lies, so it is never read as current behavior and never
counts as documenting a feature. The skill's canonical guidelines block therefore instructs
agents to redirect a design/brainstorming skill's spec output into
`docs/features/<feature>/`, mapping design sections onto the canonical files
(`README.md` for overview/REQ/AC, `flows.md`, `rules.md`, `notes.md`, and `DECISIONS.md`
for architectural decisions).

Alignment reports a design document found there as a single aggregate `WARN`
(`SPEC_OUTSIDE_FEATURE_DOCS`, R016), which persists until the folder is empty: the fix is to
migrate what is still true into the feature docs and delete the rest.

Implementation *plans* are the legitimate process artifact and may live outside
`docs/features/` (canonically `docs/superpowers/plans/`): a plan is the step sequence of one
execution, born dated and dead at merge. Plans are not part of the required set; their
absence is never a finding.

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
- Conversely, every `docs/features/<feature>/` directory must be reachable: linked from
  `docs/features/INDEX.md` (`FEATURE_NOT_IN_INDEX`) and present in the nav
  (`FEATURE_NOT_IN_NAV`), both `BLOCKER`. Nav coverage is only enforced when the nav already
  enumerates features, so file-less nav plugins are not penalized.

## Non-canonical Artifacts To Ignore

- `.DS_Store`
- `.obsidian/`
- editor-specific metadata
- OS cache files
- `docs/superpowers/specs/` — design-doc artifacts, outside the model (see
  *Feature Documentation Is The Spec*). Excluded from the audit entirely: a dead design doc
  is not maintained, so its stale links must not fail the gate.

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

For an existing file, the skill detects two sections structurally, independent of
language: a workflow section (heading + numbered step list) and a principles section
(heading + bulleted list). A file missing either shape is a `BLOCKER`; an absent file is
`INFO`. Content is not compared against the English block, so localized guidelines pass.

One content requirement is layered on top: the detected workflow section must reference
`docs/features/` (`AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED`, `BLOCKER`). Shape alone lets a
release ritual pass while saying nothing about documenting a feature. The requirement remains
language-agnostic because the path is a literal, not prose; only the workflow section counts,
and it is not reported when that section is missing altogether.

Existing AI-instruction files should also link to `docs/index.md` (the documentation map).
A missing pointer is reported as `INFO` (`AI_INSTRUCTION_MAP_POINTER_MISSING`); it is never
a `BLOCKER` and the structural shape detection is unchanged.

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
