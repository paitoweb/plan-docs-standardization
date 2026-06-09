# Design: AI Instruction Files Alignment

- Date: 2026-06-09
- Status: Approved (design)
- Skill: `plan-docs-standardization`

## Problem

The skill enforces a strict canonical documentation model (`docs/` tree + `mkdocs.yml`)
but has no awareness of AI instruction files such as `CLAUDE.md`. Teams using the
Docs-First method want their AI assistants to follow a shared "new feature" workflow
and a fixed set of working principles. Those guidelines currently live nowhere in the
skill and are not audited or proposed during alignment.

## Goal

Add a new, planning-only capability that audits existing AI instruction files and
proposes diffs to align them to a canonical guidelines block — without ever creating
the files and without ever applying changes.

## Scope and Guardrails

- The skill **never creates** AI instruction files. If a target file is absent, the
  skill only reports it (INFO) and instructs the user to create it manually.
- The skill **never applies** edits. It only emits proposed diffs, consistent with the
  existing "Hard Gate: Planning Only".
- The existing canonical docs model behavior is unchanged; this is additive.

## Target Files

Fixed paths relative to the repository root:

- `CLAUDE.md`
- `AGENTS.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`

No language detection. The canonical guidelines block is always proposed in English.

## Canonical Content (single source of truth)

A single English template:

- `assets/templates/ai-instructions/guidelines.en.md`

It contains exactly two sections, located by title:

### `## Workflow: New Feature`

Eight ordered steps; each typically corresponds to one interaction. Steps may be
combined when the feature is small. A leading **IMPORTANT** note requires verifying
prior steps before advancing, and guiding the user back to the correct step if they
ask to implement without docs, requirements, and a plan in place.

1. **Brainstorm** — align intent and technical choices with the user
   (skill `superpowers:brainstorming` or similar; using a skill is optional).
2. **Spec** — create the feature structure under `docs/features/<feature>/` (if it
   does not exist) and write it with concrete REQs/ACs.
3. **Plan** — analyze the documentation and create an implementation plan
   (skill `superpowers:writing-plans` or similar; using a skill is optional).
4. **Review** — review and approve the plan with the user.
5. **Implementation** — implement the approved plan, using TDD when applicable.
6. **Document** — update `ROADMAP.md` and `BACKLOG.md` if it makes sense,
   `DECISIONS.md` and `ARCHITECTURE.md` if the decision is architectural, any other
   documents needed based on the completed implementation, and whatever the feature
   needs under `docs/features/<feature>/`.
7. **Tests** — create/update tests (following the traceability principle) and validate
   (define the method/stack with the user).
8. **Commit & PR** — commit following conventions and open a PR referencing REQ-AC and
   linking to the feature doc (`docs/features/<feature>/`).

### `## Working Principles`

Stances, not technical rules; they complement project-specific "non-negotiable
invariants" and "NOT lists":

- **Clarify before implementing**: when in doubt, ask — never assume product
  requirements, technical requirements, engineering principles, or hard constraints.
- **Distinguish assumption from fact**: make explicit when something is your own
  conclusion, a hypothesis, or an assumption vs. established project data/rule.
- **Official docs for APIs**: for libraries and SDKs, rely only on official
  documentation — never assume signatures, methods, or behaviors.
- **Pragmatism**: be practical and direct. Do not invent out-of-scope features. Do not
  ramble.
- **traceability**: traceability is mandatory at three ends: documented requirement
  (`REQ-*` under `docs/features/`), **source code that implements a REQ cites the ID**
  (function/constant JSDoc or file header), and tests include a `// Traceability:`
  comment pointing to the doc.

The template content is a faithful English translation of the user-provided Portuguese
text, preserving the optional `superpowers:*` mentions and the references to the
canonical model.

## Audit Logic (`audit_docs_model.py`)

New function `check_ai_instruction_files(repo, findings)`:

- File absent → `INFO` / `AI_INSTRUCTION_FILE_ABSENT`
  ("skill does not create it; create manually to receive the guidelines").
- File exists, section title absent → `BLOCKER` / `AI_INSTRUCTION_SECTION_MISSING`.
- File exists, section present but divergent (normalized comparison against the
  canonical block) → `BLOCKER` / `AI_INSTRUCTION_SECTION_DIVERGENT`.
- File exists and identical to canonical → no finding.

### Divergence detection (Approach A)

Normalized comparison: trim each line, collapse consecutive blank lines, then compare
the file's section text against the canonical section text. Any difference is a
`BLOCKER`. The canonical block is treated as skill-managed; manual edits inside it will
be flagged as divergent. This matches the strict-canonical philosophy of the rest of
the skill and is idempotent (a file already aligned produces no finding).

Section extraction is by title: the section spans from its `## ` heading up to the next
`## ` heading (or end of file).

## Plan / Diff Logic (`build_docs_alignment_plan.py`)

- `AI_INSTRUCTION_FILE_ABSENT` (INFO) findings do **not** enter create/alter lists.
  They are listed under a new note: "AI instruction files absent (not created by
  design)".
- AI instruction `BLOCKER` findings enter the **Alter** list with a **real diff**
  (not the generic TODO placeholder diff):
  - section missing → diff that appends the canonical block;
  - section divergent → diff that replaces the section with the canonical block.

## Severity Map

| Scenario | Code | Severity | Plan action |
|---|---|---|---|
| File absent | `AI_INSTRUCTION_FILE_ABSENT` | INFO | Instruct manual creation |
| Section missing | `AI_INSTRUCTION_SECTION_MISSING` | BLOCKER | Diff appends canonical block |
| Section divergent | `AI_INSTRUCTION_SECTION_DIVERGENT` | BLOCKER | Diff replaces with canonical block |
| Identical | — | — | None |

## Skill Documentation Updates

- `references/compliance-rules.md`: new rules **R010** (section missing = BLOCKER),
  **R011** (section divergent = BLOCKER); INFO note for absent files; "never create"
  constraint.
- `references/docs-model-spec.md`: new section "AI Instruction Files (optional, never
  created)".
- `SKILL.md`: document the capability, target files, and the non-creation guardrail.
- `README.md`: user-facing description.

## Out of Scope

- Creating AI instruction files.
- Applying any edit automatically.
- Language detection / non-English guidelines templates.
- Auditing AI instruction files for anything beyond the two canonical sections.

## Open Questions

None.
