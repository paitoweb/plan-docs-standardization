---
name: plan-docs-standardization
description: Plan strict documentation standardization using a canonical docs model (MkDocs + docs/ tree) for new or existing repositories. Use when the user asks to create documentation from zero, audit documentation compliance, align partial docs to a shared template, enforce REQ/AC/NFR traceability, or generate a non-mutating alignment plan with proposed diffs.
disable-model-invocation: true
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
- `.resources/plan-docs-standardization/references/docs-model-spec.md`
- `.resources/plan-docs-standardization/references/compliance-rules.md`

Apply these defaults:
- Language: `en`
- Required feature files: `README.md`, `flows.md`, `rules.md`, `notes.md`
- Required root docs include `docs/reports/README.md`, `mkdocs.yml`, and `docs/requirements-mkdocs.txt`
- Ignore non-canonical artifacts: `.DS_Store`, `.obsidian`, editor/system files
- AI instruction files are optional and never created; only existing ones are audited and proposed for alignment
- Alignment is language-agnostic: feature-section expectations are inferred by strict majority of the project's own feature docs (`WARN`), and AI-instruction sections are detected structurally (`BLOCKER`); bundled templates and bootstrap stay English

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
Do not create files directly from templates; generate plan output from scripts only.

### 1) Audit compliance (read-only)

```bash
python3 .resources/plan-docs-standardization/scripts/audit_docs_model.py .
```

Optional formats:

```bash
python3 .resources/plan-docs-standardization/scripts/audit_docs_model.py . --format json
python3 .resources/plan-docs-standardization/scripts/audit_docs_model.py . --format markdown
```

### 2) Build alignment plan (read-only)

```bash
python3 .resources/plan-docs-standardization/scripts/build_docs_alignment_plan.py .
```

Optional machine format:

```bash
python3 .resources/plan-docs-standardization/scripts/build_docs_alignment_plan.py . --format json
```

## Template Usage

Use templates from `.resources/plan-docs-standardization/assets/templates/` to propose missing files in diffs.

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

**Claude Code / generic targets:** `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`.

**Cursor target:** `.cursor/rules/docs-first-workflow.mdc` (must contain workflow + principles sections structurally).

- Canonical block (English only): `.resources/plan-docs-standardization/assets/templates/ai-instructions/guidelines.en.md`
- Never create these files. If absent, emit an `INFO` finding instructing manual creation.
- If a file exists, detect workflow section (numbered steps) and principles section (bulleted list) structurally, independent of language. Missing either is a `BLOCKER`.
- Never apply changes as part of this skill.

## Escalation Policy

- Keep execution non-mutating by default.
- Do not run write operations as part of this skill.
- If a user asks to apply changes, hand off to implementation flow outside this skill after delivering the plan.
