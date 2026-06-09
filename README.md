# plan-docs-standardization

A Claude Code skill that enforces a canonical documentation model for AI-driven software development.

## What is this?

This is a reusable skill for [Claude Code](https://docs.claude.com) that implements the documentation layer of the **Docs-First** method — an approach where structured documentation leads development, and AI implements from documented decisions rather than ad hoc prompts.

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
│   └── README.md               # Reports index
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

## AI instruction files alignment

The skill can align existing AI instruction files to a canonical guidelines block:

- Target files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`
- Canonical block (English): `assets/templates/ai-instructions/guidelines.en.md`,
  containing a **Workflow: New Feature** section and a **Working Principles** section.

Behavior:

- The skill **never creates** these files. If a file is absent, it reports INFO and asks
  you to create it manually.
- For an existing file, a missing or divergent canonical section is a BLOCKER, and the
  skill proposes a diff (never applied) to add or restore the canonical block.

## Installation

### As a Claude Code user skill

1. Clone or download this repository
2. Copy the `plan-docs-standardization` folder to your Claude Code skills directory:
   ```bash
   cp -r plan-docs-standardization ~/.claude/skills/
   ```
3. The skill will be available in your Claude Code sessions

### As a project-level skill

1. Copy the folder into your project:
   ```bash
   cp -r plan-docs-standardization /your-project/.claude/skills/
   ```

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
```

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
