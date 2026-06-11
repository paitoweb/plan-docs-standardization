# Compliance Rules

## Evaluation Scope

Run checks in read-only mode over:

- `mkdocs.yml`
- `docs/**/*.md`
- `docs/requirements-mkdocs.txt`
- existing AI-instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`)

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

### R003 Feature README section consistency (WARN)

In alignment mode, the expected section set is inferred from the project's own feature
READMEs by strict majority: a section is expected when more than half of the feature
READMEs use it (compared by normalized heading text — trimmed, lowercased, accent- and
trailing-parenthetical-stripped). A feature README missing an expected section is
reported as `WARN` (`FEATURE_SECTION_INCONSISTENT`). A section unique to one richer
feature is never expected of the others, so it does not cascade. With fewer than two
feature READMEs, no consistency check runs. The skill never compares against fixed
English headings.

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

### R010 AI instruction section missing (BLOCKER)

For each existing AI instruction file, two sections are detected structurally (language
independent): a workflow section (a heading followed by a numbered list of >=3 steps) and
a principles section (a different heading followed by a bulleted list of >=3 items). A
file missing either shape is non-compliant (`AI_INSTRUCTION_SECTION_MISSING`).

### R012 AI instruction file absent (INFO)

If an AI instruction file does not exist, report it as INFO only. The skill never
creates these files.

### R013 Documentation map present (WARN)

`docs/index.md` must link to a strict majority of the navigable canonical docs
(`PROJECT_BRIEF`, `ARCHITECTURE`, `GLOSSARY`, `DECISIONS`, `ROADMAP`, `BACKLOG`,
`nfr/NON_FUNCTIONAL`, `features/INDEX`, `reports/README`). Detection is by resolved link
target (language-agnostic). Otherwise report `WARN` (`INDEX_MAP_MISSING`). Absent
`index.md` is covered by R001, not here.

### R014 AI instruction map pointer (INFO)

An existing AI-instruction file that does not link to `docs/index.md` is reported as `INFO`
(`AI_INSTRUCTION_MAP_POINTER_MISSING`). Never a `BLOCKER`.

### R015 Optional operational snapshot (local, gitignored; INFO suggestion)

`docs/reports/CURRENT_STATE.md` is optional, **local, and gitignored — never committed** (versioning
it causes churn and duplicates git's branch/last-merge). The skill never creates it. In a docs repo
(alignment mode), its absence yields a single `INFO` (`CURRENT_STATE_SUGGESTED`) recommending
adoption — never WARN/BLOCKER. The suggestion is suppressed when the user has declined it
(`snapshot_declined: true` in `.docs-first/config.yml`); recording the decline follows the same
write-on-consent rule as every other config change. On adoption, the skill ensures the file is
gitignored (and `git rm --cached` it if already tracked), with consent.

## Classification Rules

Use strict immediate alignment defaults:

- Required file missing => `BLOCKER`
- AI instruction workflow/principles section missing => `BLOCKER`
- Feature README section missing from the majority => `WARN`
- Broken traceability => `BLOCKER`
- Broken links or nav references => `BLOCKER`
- Missing documentation map in `index.md` => `WARN`
- Missing `docs/index.md` pointer in an AI-instruction file => `INFO`

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

Additionally, the skill must never create AI instruction files. For absent
`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.github/copilot-instructions.md`, output only an
INFO finding instructing manual creation.

Output only diagnostics and planning artifacts.

## Agent Profiles & State

The method is agent-agnostic; delivery is per-profile (claude/cursor/codex/generic). Each
profile declares an always-on soft target (`CLAUDE.md` / `.cursor/rules/docs-first.mdc` /
`AGENTS.md`). Active profiles come from `.docs-first/config.yml` (`profiles:`) or, absent it,
filesystem markers. Active profiles' soft targets are audited structurally like the base
AI-instruction files.

`.docs-first/config.yml` records decisions (active profiles, chosen/declined enforcement gates),
not observations. It is written only on explicit user consent; a read-only audit never writes it.

### Config validity (WARN)

When `.docs-first/config.yml` is present, unknown profile keys or unknown enforcement-gate keys
are reported as `DOCS_FIRST_CONFIG_INVALID` (`WARN`). Absent file is never a finding.

### Enforcement reconciliation

The audit compares `.docs-first/config.yml` `enforcement_chosen` against installed gate artifacts
(`.github/workflows/docs-audit.yml`, `.githooks/pre-commit`, `.claude/settings.json` with a `hooks`
key, `.codex/hooks.json`):

- A chosen gate with no artifact on disk => `ENFORCEMENT_GATE_MISSING` (`WARN`).
- No gate chosen and none present, in a docs repo (alignment mode) => `NO_ENFORCEMENT_GATE` (`INFO`).

Enforcement is never a `BLOCKER`: the skill never forces a gate.
