---
name: plan-docs-standardization
description: Plan strict documentation standardization using a canonical docs model (MkDocs + docs/ tree) for new or existing repositories. Use when the user asks to create documentation from zero, audit documentation compliance, align partial docs to a shared template, enforce REQ/AC/NFR traceability, or generate a non-mutating alignment plan with proposed diffs.
---

# Plan Docs Standardization

## Overview

Produce planning-only documentation standardization outputs.
Use a strict canonical model and return an executable alignment plan without mutating repository files.

## Hard Gate: Planning Only

- Refuse file edits, migrations, codegen, and any mutating command.
- Refuse proposing file creation diffs that would produce placeholder-only documents when no concrete writing task/content is available.
- Never bypass this guardrail. Placeholder-only file creation must remain blocked.
- If asked to implement changes, stop and provide:
  - compliance findings,
  - immediate alignment plan,
  - file create/alter list,
  - proposed diffs (not applied).
- Keep all repository inspection read-only.

## Operating Modes

- `bootstrap`: repository has no `docs/` directory.
  - Output a full baseline plan to create the canonical structure.
- `alignment`: repository already has `docs/` or `mkdocs.yml`.
  - Run strict compliance and classify every divergence as `BLOCKER`, `WARN`, or `INFO`.
  - Default policy: strict immediate alignment (`BLOCKER` for required structure/rules mismatches).

## Canonical Model

Read the canonical model from:
- `references/docs-model-spec.md`
- `references/compliance-rules.md`

Apply these defaults:
- Language: `en`
- Required feature files: `README.md`, `flows.md`, `rules.md`, `notes.md`
- Required root docs include `docs/reports/README.md`, `mkdocs.yml`, and `docs/requirements-mkdocs.txt`
- Ignore non-canonical artifacts: `.DS_Store`, `.obsidian`, editor/system files
- AI instruction files are optional and never created; only existing ones are audited and proposed for alignment
- Alignment is language-agnostic: feature-section expectations are inferred by strict majority of the project's own feature docs (`WARN`), and AI-instruction sections are detected structurally (`BLOCKER`); bundled templates and bootstrap stay English
- `docs/index.md` is a navigational ownership map (what each doc/folder is for and what must not go in it); operational session-state (branch/PR/deploy) is not design truth and lives in git/PRs or the optional `docs/reports/CURRENT_STATE.md` snapshot — never in ROADMAP/BACKLOG/DECISIONS
- Alignment adds: `INDEX_MAP_MISSING` (`WARN`) when `index.md` is not a map, and `AI_INSTRUCTION_MAP_POINTER_MISSING` (`INFO`) when an existing AI-instruction file lacks a `docs/index.md` pointer; `CURRENT_STATE.md` is optional and never created

## Required Output Shape

Always return these sections, in this order:

1. `Executive Summary`
2. `Compliance Matrix (BLOCKER/WARN/INFO)`
3. `Immediate Alignment Plan`
4. `File Create/Alter List`
5. `Proposed Diffs (not applied)`

## Workflow

1. Detect mode (`bootstrap` or `alignment`) via read-only inspection.
2. Audit structure against the canonical model.
3. Audit content rules:
   - feature README required sections,
   - ID formats (`REQ-*`, `AC-*`, `NFR-*`, `AC-NFR-*`),
   - AC-to-REQ linkage,
   - internal markdown links,
   - `mkdocs.yml` nav references.
4. Build strict findings matrix.
5. Generate immediate plan and diff proposals without applying changes.

## Scripted Operations

Prefer bundled scripts instead of ad-hoc checks.
Do not create files directly from `assets/templates/`; generate plan output from scripts only.

### 1) Audit compliance (read-only)

```bash
python3 scripts/audit_docs_model.py <repo-path>
```

Optional formats:

```bash
python3 scripts/audit_docs_model.py <repo-path> --format json
python3 scripts/audit_docs_model.py <repo-path> --format markdown
```

### 2) Build alignment plan (read-only)

```bash
python3 scripts/build_docs_alignment_plan.py <repo-path>
```

Optional machine format:

```bash
python3 scripts/build_docs_alignment_plan.py <repo-path> --format json
```

## Template Usage

Use templates from `assets/templates/` to propose missing files in diffs.

- Root docs templates: `assets/templates/docs/*`
- MkDocs template: `assets/templates/mkdocs.yml`
- Feature templates: `assets/templates/docs/features/_feature_/*`

Default guardrail:
- Do not emit `create` diffs if rendered content still depends on placeholder text and no concrete content-writing task was provided.
- In these cases, keep the file in the create list and mark it as deferred (`deferred creation`) with reason.
- Do not emit placeholder-based scaffolding.

Template tokens available:
- `{{PROJECT_NAME}}`
- `{{FEATURE_NAME}}`
- `{{FEATURE_ID}}`
- `{{LAST_UPDATED}}`

## AI Instruction Files Alignment

Optionally align existing AI instruction files to the canonical guidelines block.

- Base target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`.
- Plus each active agent profile's soft target (see `## Agent Profiles`): Cursor adds
  `.cursor/rules/docs-first.mdc`; Codex/generic use `AGENTS.md`.
- Canonical block (English only): `assets/templates/ai-instructions/guidelines.en.md`,
  with sections `## Workflow: New Feature` and `## Working Principles`.
- Never create these files. If absent, emit an `INFO` finding instructing manual creation.
- If a file exists, the skill detects a workflow section (numbered steps) and a principles
  section (bulleted list) structurally, independent of language. Missing either is a
  `BLOCKER`; the proposed diff appends the English canonical block as a starting point to
  translate. Never apply changes.

## Agent Profiles

The canonical method is single and agnostic; only *delivery* varies per AI agent.
A profile customizes where the always-on instruction lives and how the skill is
packaged — never the docs model or the method.

| Profile | Always-on soft target | Skill package dir |
|---|---|---|
| claude | `CLAUDE.md` | `.claude/skills/plan-docs-standardization/` |
| cursor | `.cursor/rules/docs-first.mdc` (frontmatter `alwaysApply: true`) | `.cursor/skills/plan-docs-standardization/` |
| codex | `AGENTS.md` | `.agents/skills/plan-docs-standardization/` |
| generic | `AGENTS.md` | (none) |

**Detect → ask → persist (first thing the skill does):**

1. Read `.docs-first/config.yml`. If it lists `profiles`, use them (authoritative).
2. Else detect by filesystem markers (`.claude/`, `.cursor/`, `.codex/`, `.agents/`).
3. Else ask the user which agent(s) they use. Never guess from model self-identification.
4. After resolving (and only with the user's consent), persist the decision:
   preview `render_config(...)` then write via `save_config(...)`. A read-only audit
   never writes this file. Record decisions, not observations (do not store "`.cursor/` exists").

**Multiple agents in one repo:** `profiles` is a list. When several are active, propose each
profile's soft target together; the docs tree and audit are shared.

**Soft-layer install offer:** soft targets are never auto-created (absent → INFO). When a profile
is active and its surface is absent, offer to install it with consent — for Cursor, generate the
rule with `python3 scripts/render_profile_artifacts.py cursor > .cursor/rules/docs-first.mdc`.
For Claude/Codex, append the canonical block to the user's existing `CLAUDE.md`/`AGENTS.md`.

**State file validation:** the audit reads `.docs-first/config.yml` when present and reports
`DOCS_FIRST_CONFIG_INVALID` (`WARN`) for unknown profile or enforcement-gate keys. Absent file
is never a finding.

## Enforcement Gates

Instructions are *soft* (they shape the agent but it can drift). True enforcement is a
*deterministic gate* that runs the audit outside the model. Gates are **never forced**.

Gate options (all run the docs audit; `audit_cmd` points at the installed audit script):

| Gate key | Artifact | Strength | Scope |
|---|---|---|---|
| `ci` | `.github/workflows/docs-audit.yml` + branch protection | unbypassable (real gate) | team-wide |
| `local-hook` | `.githooks/pre-commit` (+ `git config core.hooksPath .githooks`) | bypassable (`--no-verify`) | per dev |
| `claude-hooks` | `.claude/settings.json` Stop hook | in-session (Claude only) | per dev |
| `codex-hooks` | `.codex/hooks.json` PreToolUse deny | in-session (Codex only) | per repo |

**Consent flow (never force):**

1. **Never obligate** a gate.
2. **Warn, concretely:** no gate → docs drift silently and eventually lie; soft-only → fails
   under pressure (big PR, deadline); local-hook only → bypassable, and teammates without it commit
   non-compliant code.
3. **Ask which to adopt, leading with a recommendation:** CI + branch protection, plus the local
   hook; add native hooks where the agent offers them.
4. **Instruct + offer to install, with a preview** of every file write / config change / `gh api`
   call before acting. Generate artifacts with `enforcement_gates.render_*`. Branch protection is a
   repo setting, not a file: `gh api -X PUT repos/{owner}/{repo}/branches/main/protection ...`
   (needs admin); degrade gracefully (generate the workflow, instruct the manual toggle) when the
   token lacks rights.

**Claude settings location:** the `claude-hooks` gate is committed to `.claude/settings.json`
(shared with the team). If the user instead opts to put it in `.claude/settings.local.json` — the
personal, machine-local variant — that file must **not** be committed: ensure it is gitignored
(add `.claude/settings.local.json` to `.gitignore`, offered with consent) before writing the hook
there.

**Persisted choices:** record accepted gates in `.docs-first/config.yml` `enforcement_chosen` and
refusals in `enforcement_declined` (never re-ask). The audit then reconciles intent vs reality
(see below). Native hook configs follow documented schemas — verify against the installed tool.

## Operational Snapshot (CURRENT_STATE.md)

`docs/reports/CURRENT_STATE.md` is an **optional, local, gitignored** scratchpad for operational
session-state (where you are, next action, deploy state). It is **never committed**: versioning it
creates churn (a committed snapshot trails its own merge — "last merge = this very PR" is stale the
moment it lands) and duplicates what git already knows (branch, last merge). Versioned history lives
in git and PR descriptions.

- The audit suggests it when absent in a docs repo (`CURRENT_STATE_SUGGESTED`, INFO); suppress with
  `snapshot_declined: true` in `.docs-first/config.yml`.
- **On adoption, keep it local (offer with consent):** add `docs/reports/CURRENT_STATE.md` to
  `.gitignore`; if it is already tracked, also run `git rm --cached docs/reports/CURRENT_STATE.md`
  (keeps the file on disk, stops tracking it).
- The canonical block tells agents to update it as they work and to consult it first when the user
  asks where things stand / what is next.

## Escalation Policy

- Keep execution non-mutating by default.
- Do not run write operations as part of this skill.
- If a user asks to apply changes, hand off to implementation flow outside this skill after delivering the plan.
