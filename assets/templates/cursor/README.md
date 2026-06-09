# Cursor Docs-First Setup

Install the Docs-First method in a Cursor project using files from this template bundle.

## Prerequisites

Link the `plan-docs-standardization` skill repository into your project:

```bash
mkdir -p .resources
ln -sf ../../plan-docs-standardization .resources/plan-docs-standardization
```

Adjust the symlink target if the repo lives elsewhere.

## Install

From the `plan-docs-standardization` repository root:

```bash
PROJECT=/path/to/your-project

mkdir -p "$PROJECT/.cursor/rules"
mkdir -p "$PROJECT/.cursor/commands"
mkdir -p "$PROJECT/.cursor/skills/plan-docs-standardization"

cp assets/templates/cursor/rules/docs-first-workflow.mdc "$PROJECT/.cursor/rules/"
cp assets/templates/cursor/rules/docs-first-implementation.mdc "$PROJECT/.cursor/rules/"
cp assets/templates/cursor/commands/*.md "$PROJECT/.cursor/commands/"
cp assets/templates/cursor/skills/plan-docs-standardization/SKILL.md \
   "$PROJECT/.cursor/skills/plan-docs-standardization/"
cp assets/templates/docs/traceability.json "$PROJECT/docs/"  # edit feature globs after bootstrap
```

## Usage in Cursor

| Trigger | Purpose |
|---------|---------|
| `/docs-bootstrap` | Plan canonical docs structure for a new project |
| `/docs-audit` | Full compliance audit (docs + code traceability) and alignment plan |
| Skill `plan-docs-standardization` | Same planning workflow, invoked by name |

The always-on rule `.cursor/rules/docs-first-workflow.mdc` enforces the Docs-First workflow and working principles in every session. File-specific rule `.cursor/rules/docs-first-implementation.mdc` applies when editing source or test files.

## Claude Code parity

Claude Code installation is unchanged. See the repository root `README.md` for `~/.claude/skills/` and `CLAUDE.md` setup.

Cursor uses `.cursor/rules/docs-first-workflow.mdc` instead of `CLAUDE.md` for the canonical workflow/principles block.
