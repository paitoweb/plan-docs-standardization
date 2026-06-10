# Design: Self-Describing Docs Model (Ownership Map + Operational State)

- Date: 2026-06-10
- Status: Approved (design)
- Skill: `plan-docs-standardization`

## Problem

The canonical model does not teach an implementing project's agents what each
file/folder is for or where new content belongs. In a real project this gap caused an
agent to spontaneously create `docs/STATUS.md` — a 520-line append-only changelog that
overlapped `ROADMAP.md` and `BACKLOG.md` and leaked operational state into the plan docs
(ROADMAP carrying live status, BACKLOG carrying deploy versions).

The root cause is not a missing file. It is that the model is silent on two things:

1. **Ownership** — what each canonical doc/folder answers, and the hard boundary that
   operational session-state (branch / PR / deploy version / next physical action /
   last-session narrative) is **not** design truth.
2. **A home for operational state** — there is a legitimate need for a "where are we now,
   what's the next action" handoff that `git log` (shows what changed, not where we
   stopped) and the forward-looking plan docs do not serve. With no sanctioned home,
   agents improvise badly.

## Goal

Make the docs model **self-describing**: a durable ownership map in `docs/`, a behavioral
directive in the AI-instruction guidelines block that points to it, and an optional living
handoff snapshot in `docs/reports/`. Enforcement is **lenient** — bootstrap generates the
new material; alignment warns/infos but never blocks and never breaks projects that pass
today.

## Decisions (locked in brainstorming)

1. One unified feature: "self-describing docs model".
2. The map is split: a durable reference lives in `docs/index.md`; a behavioral directive
   + pointer lives in the AI-instruction guidelines block.
3. Operational state becomes an **optional** living report `docs/reports/CURRENT_STATE.md`
   (INFO tier), a rewritten snapshot — never append-only. Not promoted to a required
   canonical doc.
4. Enforcement is lenient: bootstrap emits the map; alignment is `WARN` (docs) / `INFO`
   (AI-instructions), never `BLOCKER`. No retroactive breakage.
5. The durable map lives as a section inside the already-required `docs/index.md` (no new
   required file).

## Behavior

### 1. Durable ownership map in `docs/index.md`

The bootstrap `index.md` template gains a **Documentation Map** table covering every
canonical doc/folder with columns (English baseline in the bundled template; project
language otherwise): *Answers / Granularity / Cadence / Do not put here*. Below it, a
short **boundary rule**: operational session-state (branch, PR, deploy version, next
physical action, last-session narrative) is not design truth — it never goes in
ROADMAP/BACKLOG/DECISIONS; narrative history lives in git + PRs.

Canonical map rows: `index.md`, `PROJECT_BRIEF.md`, `ARCHITECTURE.md`, `GLOSSARY.md`,
`DECISIONS.md`, `ROADMAP.md`, `BACKLOG.md`, `nfr/NON_FUNCTIONAL.md`, `features/<f>/`,
`reports/`.

**Alignment detection (language-agnostic, `WARN`).** A new check
`check_index_map(repo, findings)` confirms `docs/index.md` contains a *navigational map*:
markdown links that resolve to a **strict majority** of the navigable canonical docs
(the canonical set minus `index.md` itself, `requirements-mkdocs.txt`, and `mkdocs.yml`).
Detection is by **link target**, not by words or column richness, so it is
language-agnostic and reuses the existing strict-majority idiom. New finding code
`INDEX_MAP_MISSING` at `WARN`.

> Accepted limitation: the `WARN` only catches "no map at all". It does not audit the
> richer columns (responde/cadência/NÃO) language-agnostically — those are delivered via
> the bootstrap template, the AI-instruction directive, and `docs-model-spec.md` guidance.
> Auditing column richness is explicitly out of scope. The current bundled `index.md`
> template already links all canonical docs, so projects scaffolded from it pass with no
> regression.

### 2. Behavioral directive in the AI-instruction guidelines block

`assets/templates/ai-instructions/guidelines.en.md` gains a third section
`## Documentation Map` alongside `## Workflow: New Feature` and `## Working Principles`.
It is behavioral guidance (not a reference table):

- Before writing docs, consult the map in `docs/index.md` to find the right home.
- Feature → `docs/features/<feature>/`. Architectural decision → `DECISIONS.md`.
  Strategy/phase → `ROADMAP.md`. Queue/priority → `BACKLOG.md`.
- Operational session-state never goes in plan docs. To track it, use the optional
  `docs/reports/CURRENT_STATE.md` snapshot (rewritten, not accumulated). History → git/PRs.
- **Do not invent new top-level docs.** If something has no home in the map, propose
  adding it to the map first. *(This is the direct guard against spontaneous STATUS.md.)*

**Alignment detection (language-agnostic, `INFO`).** Existing AI-instruction files are
checked for a **pointer**: a markdown reference to `docs/index.md`. Absence emits a new
`INFO` finding `AI_INSTRUCTION_MAP_POINTER_MISSING`. This is detected by link target, not
by a third structural shape — `detect_ai_instruction_shapes` is unchanged, so no file that
passes today becomes a `BLOCKER`. Absent files keep emitting the existing
`AI_INSTRUCTION_FILE_ABSENT` `INFO`; the skill still never creates them.

### 3. Optional operational snapshot `docs/reports/CURRENT_STATE.md`

A new template with a fixed shape and a discipline banner at the top. The bundled
template is **English** (like every other bundled template); the labels below are the
English baseline:

- Banner: *"Present-state snapshot. Rewritten every session — NOT append-only.
  History → git/PRs."*
- **Where we are** (3–5 lines): branch, last merge, next action.
- **Deploy state**: PROD x / DEV y.
- **Active pending items**: links to `BACKLOG.md` (no content duplication).
- **Open decisions**: links to `DECISIONS.md`.

It is **optional**: not in `REQUIRED_FILES`, not in the bootstrap baseline create list, and
its absence never produces a finding. The skill never auto-creates it; the AI-instruction
directive tells the agent to create it on demand. `docs/reports/README.md` gains one line
noting `reports/` now hosts two genres: point-in-time reports and the optional living
snapshot.

## Severity Map (new/changed)

| Scenario | Code | Severity |
|---|---|---|
| `docs/index.md` lacks a navigational map (links to < majority of canonical docs) | `INDEX_MAP_MISSING` | WARN |
| Existing AI-instruction file lacks a `docs/index.md` pointer | `AI_INSTRUCTION_MAP_POINTER_MISSING` | INFO |
| `docs/reports/CURRENT_STATE.md` absent | — (no finding; optional) | — |

Unchanged: `AI_INSTRUCTION_SECTION_MISSING` (BLOCKER), `AI_INSTRUCTION_FILE_ABSENT` (INFO),
`FEATURE_SECTION_INCONSISTENT` (WARN), and all required-file/traceability checks.

## Plan / Diff

`build_docs_alignment_plan.py`:

- Route `INDEX_MAP_MISSING` to the **alter** list for `docs/index.md` and propose
  appending the Documentation Map block (concrete content from the bundled template — not
  placeholder, so the no-placeholder guardrail is satisfied).
- Route `AI_INSTRUCTION_MAP_POINTER_MISSING` to **alter** for the AI-instruction file and
  propose appending the `## Documentation Map` section from `guidelines.en.md` as a
  starting point to translate (consistent with existing AI-instruction alignment, never
  applied). Add it to the non-ignored action codes.
- When an AI-instruction file already triggers `AI_INSTRUCTION_SECTION_MISSING`, the
  appended canonical block now includes the new `## Documentation Map` section, since it is
  part of `guidelines.en.md`.

## Components / Files

- `scripts/audit_docs_model.py`:
  - Add `check_index_map(repo, findings)`: strict-majority link-target detection over the
    navigable canonical set; emit `INDEX_MAP_MISSING` (`WARN`). Reuse existing link
    resolution (`iter_markdown_links` / `resolve_link_target`).
  - Add a `docs/index.md` pointer check inside `check_ai_instruction_files` (for existing
    files only): emit `AI_INSTRUCTION_MAP_POINTER_MISSING` (`INFO`) when no link resolves
    to `docs/index.md`. `detect_ai_instruction_shapes` is untouched.
  - Wire both checks into `audit_repository`.
- `scripts/build_docs_alignment_plan.py`:
  - Add diff generation for `INDEX_MAP_MISSING` (append map block to `index.md`) and route
    `AI_INSTRUCTION_MAP_POINTER_MISSING` to append the Documentation Map section.
- `assets/templates/docs/index.md`: add the Documentation Map table + boundary rule.
- `assets/templates/ai-instructions/guidelines.en.md`: add `## Documentation Map` section.
- `assets/templates/docs/reports/CURRENT_STATE.md`: new optional template (banner + four
  sections).
- `assets/templates/docs/reports/README.md`: add the two-genres line.
- `assets/templates/docs/ROADMAP.md`, `assets/templates/docs/BACKLOG.md`: add a one-line
  scope banner reinforcing the boundary ("do not include operational state here").
- `references/docs-model-spec.md`: add a **Documentation Ownership Map** section (canonical
  table + boundary rule); register `docs/reports/CURRENT_STATE.md` as optional/INFO; note
  the `index.md` map expectation and the AI-instruction pointer.
- `references/compliance-rules.md`: add rules for `INDEX_MAP_MISSING` (`WARN`) and
  `AI_INSTRUCTION_MAP_POINTER_MISSING` (`INFO`); state `CURRENT_STATE.md` is optional and
  never a finding.
- `SKILL.md`, `README.md`: document the self-describing map, the operational-state home,
  and the lenient enforcement.
- Tests (`tests/`):
  - `INDEX_MAP_MISSING` is `WARN` when `index.md` lacks links to a majority of canonical
    docs; no finding when the template-style map is present.
  - `AI_INSTRUCTION_MAP_POINTER_MISSING` is `INFO` when an existing AI-instruction file has
    no `docs/index.md` link; no finding when the pointer is present; an AI-instruction file
    with workflow+principles but no pointer still does **not** emit a `BLOCKER`.
  - `docs/reports/CURRENT_STATE.md` absence never produces a finding.
  - Bootstrap plan output includes the map (in `index.md`) and the `## Documentation Map`
    section (in the AI-instruction block).

## Out of Scope

- Promoting any operational-state doc to a required/`BLOCKER` canonical file.
- Auditing the richness of the map columns (responde/cadência/NÃO) — only the presence of
  a navigational map is checked.
- Making the `## Documentation Map` section a third structurally-required AI-instruction
  shape (would retroactively break passing files).
- Auto-creating `CURRENT_STATE.md` or any AI-instruction file.
- Configurable thresholds (strict majority is the fixed rule, matching existing checks).

## Open Questions

None.
