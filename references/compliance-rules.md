# Compliance Rules

## Evaluation Scope

Run checks in read-only mode over:

- `mkdocs.yml`
- `docs/**/*.md`
- `docs/requirements-mkdocs.txt`

Ignore non-canonical paths:

- files named `.DS_Store`
- any path containing `.obsidian/`
- hidden OS/editor artifacts

## Rule Set

### R001 Required root files (BLOCKER)

All canonical root files must exist.

### R002 Required feature files (BLOCKER)

Every `docs/features/<feature>/` directory must contain:
- `README.md`
- `flows.md`
- `rules.md`
- `notes.md`

### R003 Feature README minimum sections (BLOCKER)

A feature README missing any required section is non-compliant.

### R004 ID format validity (BLOCKER)

ID tokens must follow regex patterns:

- `REQ-[A-Z0-9-]+-[0-9]{3}`
- `AC-[A-Z0-9-]+-[0-9]{3}`
- `NFR-[0-9]{3}`
- `AC-NFR-[0-9]{3}`

### R005 AC traceability (BLOCKER)

Feature AC headings must reference at least one REQ ID in the same file.

### R006 AC-NFR traceability (BLOCKER)

NFR AC headings must reference at least one NFR ID in the same file.

### R007 Internal markdown links (BLOCKER)

All internal links must resolve to existing targets.

### R008 MkDocs nav references (BLOCKER)

All markdown file paths in `mkdocs.yml` nav must resolve under `docs/`.

### R009 Optional quality observations (WARN/INFO)

Non-fatal context can be reported as WARN/INFO, for example:

- low coverage of reports indexing
- inconsistent naming conventions that still resolve

## Classification Rules

Use strict immediate alignment defaults:

- Required file missing => `BLOCKER`
- Required section missing => `BLOCKER`
- Broken traceability => `BLOCKER`
- Broken links or nav references => `BLOCKER`

No phased convergence by default.

## Plan Generation Rules

When generating the plan:

1. Group by severity (`BLOCKER`, then `WARN`, then `INFO`).
2. Prioritize structure blockers before content blockers.
3. Produce file create/alter lists.
4. Produce proposed diffs for missing files using templates only when the rendered output is not placeholder-only.
5. If a missing file can only be scaffolded with placeholders and there is no explicit writing task/content, mark as deferred creation with reason (do not emit create diff).
6. Do not apply changes.

## Non-Mutation Constraint

The compliance scripts and skill execution must not:

- edit files
- run formatters in write mode
- run code generation that mutates tracked files
- run migration commands

Output only diagnostics and planning artifacts.
