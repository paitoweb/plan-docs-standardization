# plan-docs-standardization

An AI coding agent skill that enforces a canonical documentation model for AI-driven software development. Works with **Claude Code**, **Cursor**, **Codex**, and any agent that reads a skills directory.

## What is this?

This is a reusable [agent skill](https://docs.claude.com) that implements the documentation layer of the **Docs-First** method — an approach where structured documentation leads development, and AI implements from documented decisions rather than ad hoc prompts.

The canonical method (the docs model, the audit, the traceability rules) is **agent-agnostic**. Only *delivery* varies per agent — where the always-on instruction lives and how the skill package is hosted. The skill detects which agent(s) your repo uses and adapts automatically.

📖 **Read the full article about the Docs-First method:** [Link to article]

## Why documentation-first?

When building software with AI, the most common problem isn't bad code — it's **regressions**. AI has no persistent memory. Every prompt is a blank slate. Without structured context, the AI "invents" solutions that break existing features.

This skill solves that by enforcing a strict documentation standard that serves as the AI's external memory: architecture, requirements, acceptance criteria, business rules, flows, technical notes — all traceable, all interlinked.

## What the skill does

Given a project (new or existing), the skill:

1. **Detects mode**: `bootstrap` (no docs exist) or `alignment` (docs exist but may not conform)
2. **Audits** the documentation structure against a canonical model
3. **Classifies findings** as `BLOCKER`, `WARN`, or `INFO`
4. **Generates an alignment plan** with proposed diffs — without modifying any files

The skill is **planning-only by design**. It never mutates your repository. It proposes; you decide.

## Canonical documentation model

The skill enforces the following structure:

```
docs/
├── index.md                    # Documentation home
├── PROJECT_BRIEF.md            # Vision, audience, goals
├── ARCHITECTURE.md             # Technical structure, data model, diagrams
├── GLOSSARY.md                 # Domain terms
├── DECISIONS.md                # ADRs (Architectural Decision Records)
├── ROADMAP.md                  # Delivery phases
├── BACKLOG.md                  # Prioritized items
├── nfr/
│   └── NON_FUNCTIONAL.md       # NFRs with acceptance criteria
├── features/
│   ├── INDEX.md                # Feature index
│   └── <feature>/
│       ├── README.md           # Requirements (REQ-*) + Acceptance Criteria (AC-*)
│       ├── flows.md            # Mermaid flowcharts
│       ├── rules.md            # Business rule decision tables
│       └── notes.md            # Technical implementation notes
├── reports/
│   ├── README.md               # Reports index
│   └── CURRENT_STATE.md        # Optional living state snapshot (rewritten each session)
└── requirements-mkdocs.txt     # Python deps for MkDocs
mkdocs.yml                      # MkDocs configuration
```

### ID conventions

| Type | Format | Example |
|------|--------|---------|
| Functional requirement | `REQ-<FEATURE>-NNN` | `REQ-TASK-MGMT-001` |
| Acceptance criterion | `AC-<FEATURE>-NNN` | `AC-TASK-MGMT-001` |
| Non-functional requirement | `NFR-NNN` | `NFR-001` |
| NFR acceptance criterion | `AC-NFR-NNN` | `AC-NFR-001` |

### Traceability rules

- Every AC must reference at least one REQ in the same feature
- Every AC-NFR must reference at least one NFR
- All internal markdown links must resolve
- All `mkdocs.yml` nav references must resolve
- And the reverse direction: every feature folder must be reachable — linked from
  `docs/features/INDEX.md` and present in the nav (both BLOCKER). A feature the reader
  cannot find is undocumented in practice. Nav coverage is only enforced when your nav
  already lists features, so file-less nav plugins (awesome-pages, literate-nav) are not
  penalized. **Breaking change** if you documented features without indexing them.

### Documentation map and operational state

`docs/index.md` is a navigational map: it documents what each file/folder answers and what
must not go in it. Operational session-state (branch, PR, deploy version, next action) is
not design truth — it never goes in ROADMAP/BACKLOG/DECISIONS; it lives in git/PRs or, if
you want a readable "where are we now" pointer, in the optional `docs/reports/CURRENT_STATE.md`
snapshot (rewritten each session, never append-only). In alignment mode the skill warns
(`INDEX_MAP_MISSING`) when `index.md` is not a map and reports INFO
(`AI_INSTRUCTION_MAP_POINTER_MISSING`) when an existing AI-instruction file lacks a pointer
to the map.

> **Language:** Bundled templates are English and bootstrap scaffolds English. In
> alignment mode the skill is language-agnostic — it infers feature-section expectations
> from the project's own docs and detects AI-instruction sections structurally, so docs in
> any language pass without false blockers.

## AI instruction files alignment

The skill can align existing AI instruction files to a canonical guidelines block:

- Target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`
- Canonical block (English): `assets/templates/ai-instructions/guidelines.en.md`,
  containing a **Workflow: New Feature** section and a **Working Principles** section.

Behavior:

- The skill **never creates** these files. If a file is absent, it reports INFO and asks
  you to create it manually.
- For an existing file, the skill detects a workflow section (numbered steps) and a
  principles section (bulleted list) by structure, independent of language. Missing either
  is a BLOCKER; the proposed diff (never applied) appends the English canonical block as a
  starting point to translate.
- The workflow section must also **reference `docs/features/`**, or it is a BLOCKER
  (`AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED`). Detection stays language-agnostic because the
  path is a literal, so a localized workflow passes by citing it. Structure alone is too
  weak: any numbered list of three steps — a release ritual, for instance — satisfies it
  while never telling the agent to document a feature.

> **Breaking change.** If your `CLAUDE.md`/`AGENTS.md` never received the canonical block,
> it audits green on earlier versions of this skill and becomes a BLOCKER on upgrade. This
> is intentional: it is the case where the docs model was installed but the always-on
> instruction that drives it never was. Fix by appending the canonical block (the skill
> proposes the diff) or by adding a `docs/features/` step to your own workflow section.

## Installation

The method is single; only *delivery* varies per agent. Each agent has a **soft target**
(the always-on instruction surface) and a **skill package directory** (where the skill is hosted):

| Agent | Always-on soft target | Skill package directory |
|-------|----------------------|-------------------------|
| Claude Code | `CLAUDE.md` | `.claude/skills/plan-docs-standardization/` |
| Cursor | `.cursor/rules/docs-first.mdc` (`alwaysApply: true`) | `.cursor/skills/plan-docs-standardization/` |
| Codex | `AGENTS.md` | `.agents/skills/plan-docs-standardization/` |
| Generic | `AGENTS.md` | — (no hosted package) |

First clone or download this repository, then follow the section for your agent.

### Claude Code

Copy the skill folder to your user skills directory (available in every session):

```bash
cp -r plan-docs-standardization ~/.claude/skills/
```

Or scope it to a single project:

```bash
cp -r plan-docs-standardization /your-project/.claude/skills/
```

### Cursor

**Cursor v2.4+** reads `.claude/skills/` natively — if you already installed the skill for
Claude Code (user or project level), Cursor picks it up automatically; nothing else to do.

To host it under Cursor's own skills directory instead:

```bash
cp -r plan-docs-standardization /your-project/.cursor/skills/
```

Optionally generate the always-on rule so the Docs-First workflow is applied on every request:

```bash
python3 plan-docs-standardization/scripts/render_profile_artifacts.py cursor \
  > /your-project/.cursor/rules/docs-first.mdc
```

This writes a `.mdc` rule with `alwaysApply: true` containing the canonical
**Workflow: New Feature** and **Working Principles** blocks.

### Codex

Copy the skill folder into the agents skills directory:

```bash
cp -r plan-docs-standardization /your-project/.agents/skills/
```

The always-on instruction surface is `AGENTS.md`. Generate the canonical block to append:

```bash
python3 plan-docs-standardization/scripts/render_profile_artifacts.py codex
```

### Generic agent

Any agent that reads an instructions file can use the method. Generate the canonical
guidelines block and add it to your agent's instruction file (e.g. `AGENTS.md`):

```bash
python3 plan-docs-standardization/scripts/render_profile_artifacts.py generic
```

> The skill **never auto-creates** soft-target files. When a target is absent it reports
> an `INFO` finding and offers to install it with your consent — it does not write without asking.

## Usage

### Bootstrap a new project

```
/plan-docs-standardization Let's start a new project called MyApp. 
It should be a web application for [description]. 
Create the initial project structure and documentation.
```

The skill will generate a complete documentation plan based on your description.

### Audit an existing project

```
/plan-docs-standardization Audit the documentation in this repository 
and create an alignment plan.
```

The skill will analyze your existing docs and produce a compliance matrix with proposed fixes.

### Scripted operations

The skill includes Python scripts for automated auditing:

```bash
# Audit documentation compliance (read-only)
python3 scripts/audit_docs_model.py /path/to/repo

# Build alignment plan (read-only)
python3 scripts/build_docs_alignment_plan.py /path/to/repo

# Output as JSON for tooling integration
python3 scripts/audit_docs_model.py /path/to/repo --format json

# PR-time code<->docs check (opt-in): fails when the diff touches code
# but nothing under docs/features/. Default base is origin/main.
python3 scripts/audit_docs_model.py /path/to/repo --diff
python3 scripts/audit_docs_model.py /path/to/repo --diff upstream/dev
```

`--diff` exists because the rest of the audit only reads `docs/` — a feature can ship fully
implemented and fully undocumented while every rule passes. It reads changed *paths* only
(`git diff --name-only`), never file contents outside `docs/`.

Defaults chosen to avoid crying wolf: only source extensions count as code (a lockfile bump
or CI tweak does not), and test paths are exempt since a test-only change ships no behavior.
Tune with `code_extensions` and `diff_exempt_globs` in `.docs-first/config.yml`; exempt an
individual change with `docs-first: skip` in a commit message. An unresolvable base is a WARN,
never a BLOCKER.

### Code-to-docs coverage

`--diff` catches the moment a change lands. For code that is *already* shipped and
undocumented, the audit reads directory names under your code roots (never file contents):

```yaml
# .docs-first/config.yml
feature_map: [src/voice=voice-transcription, src/tree=file-tree]
code_roots: [src, packages]     # optional; defaults to src/lib/app/apps/packages/...
coverage_min: 50                # optional threshold for the ratio finding
coverage_gate: false            # true promotes the ratio WARN to a BLOCKER
```

A mapped path that exists with no matching feature doc is a **BLOCKER** — you declared the
mapping, so there is nothing to infer. Beyond the map, one aggregate **WARN** reports the
ratio of candidate code units to documented features.

That ratio is a smell signal, not a measurement: candidates are directories, and a layered
architecture (`main/`, `renderer/`, `components/`, `hooks/`) has directories per layer, not per
feature. It is deliberately one finding rather than one per directory — an audit that marks
every folder teaches you to ignore it. `feature_map` is the precise instrument.

### Migrating legacy design docs

If you have design docs from a brainstorming workflow (`docs/superpowers/specs/`) and no
feature docs, the plan emits a migration worklist: one row per design doc with a candidate
slug and the four target files — structure only, all deferred, never a create diff.

**The spec is a lead; the code is the source.** A dated design doc drifts from the
implementation, so transcribing it moves stale claims into the one place that must not lie.
Today the stale spec is visibly history; migrated unchecked, it becomes "current truth" lying
with authority. So: read the code, write the four files from what it actually does, and mark
anything you could not confirm with `docs-first:unverified`.

Those markers are tracked (`FEATURE_DOC_UNVERIFIED`, WARN, one per feature) so they cannot age
into truth unnoticed — a marker nobody follows up on is worse than none. The finding clears
when the last one is removed. It never blocks, so migration can be incremental.

## The Docs-First cycle

This skill is the starting point of a broader development method:

```
Concept/Need
      ↓
Structured documentation  ← THIS SKILL
      ↓
Gap audit → Human decisions
      ↓
Consolidated documentation
      ↓
Implementation plan → Human approval
      ↓
Guided implementation
      ↓
Reverse synchronization (code → docs)
      ↓
Tests (derived from requirements and acceptance criteria)
      ↓
Next increment...
```

## Real-world results

Using this skill and the Docs-First method on a real project (Slidoo — a gesture-based task management app):

- **36 documentation files** generated in ~8 minutes from concept images
- **MVP implemented** in ~15 minutes: 22 source files, 41 tests, all passing
- **84 tests** across 9 files, all traceable to specific requirements
- **Cross-platform**: same documentation adapted from React (web) to Swift/SwiftUI (macOS desktop), preserving all requirements and business logic

## License

MIT

## Author

Fabrício Santos — [LinkedIn](https://linkedin.com/in/YOUR_PROFILE) | [Twitter/X](https://x.com/YOUR_HANDLE)
