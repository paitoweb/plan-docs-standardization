# Compliance Rules

## Evaluation Scope

Run checks in read-only mode over:

- `mkdocs.yml`
- `docs/**/*.md`
- `docs/requirements-mkdocs.txt`
- existing AI-instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`)
- `.docs-first/config.yml` when present
- code **directory names** under the resolved code roots — existence only, never file
  contents (R019)
- in `--diff` mode only: the list of paths changed against the diff base, read with
  `git diff --name-only` (read-only; file contents outside `docs/` are never read)

Ignore non-canonical paths:

- files named `.DS_Store`
- any path containing `.obsidian/`
- hidden OS/editor artifacts
- everything under `docs/superpowers/specs/` — design-doc artifacts are outside the model
  (`docs/features/` is the single source of truth for feature behavior). The subtree is not
  audited at all: a dated design doc is abandoned by definition, so its stale internal links
  must never produce a `BROKEN_INTERNAL_LINK` blocker.

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

### R011 Workflow must route through `docs/features/` (BLOCKER)

Structure alone is not enough: R010 accepts any level-2 section with three ordered items, so
a release ritual passes while saying nothing about documenting a feature. A detected workflow
section that does not reference `docs/features/` is therefore non-compliant
(`AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED`).

The check stays language-agnostic because `docs/features/` is a literal path, not natural
language — the same trick R014 uses with resolved link targets. A localized workflow passes
by citing the path (`2. Doc da feature em docs/features/<feature>/`).

Scope is the workflow section only, not the whole file: a mention in an unrelated appendix
does not make the *process* route through the feature doc. When the workflow section is
absent entirely, only R010 fires — the missing reference is not reported on top of it.

**Breaking change.** A repository whose AI-instruction file never received the canonical
block audits green today and turns `BLOCKER` on upgrade. That is the intent of the rule.

### R021 Canonical block staleness (WARN/INFO)

The canonical block is a single source of truth that is **copied** into each consumer
repository, never linked. Copies drift the moment the source changes, and nothing else
detects it: R010 (shape) and R011 (path reference) both keep passing on a block that is two
revisions old. This is the dated-design-doc pathology one level up — a copied artifact nobody
reconciles with its source.

The block carries a version marker, `<!-- docs-first-block: N -->`, compared against
`CANONICAL_BLOCK_VERSION`:

| Installed | Finding | Severity |
|---|---|---|
| equal | none | — |
| older | `AI_INSTRUCTION_BLOCK_STALE` | `WARN` |
| absent | `AI_INSTRUCTION_BLOCK_UNVERSIONED` | `INFO` |
| newer | `AI_INSTRUCTION_BLOCK_AHEAD` | `INFO` |

Absent is `INFO`, not `WARN`: every repository alive at the time of introduction is unmarked,
and a `WARN` would fire on all of them at once. Newer means the *skill* is behind, so the
message points at updating the skill rather than editing the repo.

**The marker lives inside the workflow section**, not above it. The skill installs the block
by appending its sections, so a marker in the preamble would never reach a consumer — the
versioning would be invisible in exactly the repos it is meant to serve.

**It is language-neutral**, so localized guidelines are unaffected: translate the block and
keep the marker for the version you translated. A hand-written file simply reports the `INFO`
until it adopts one.

Nothing is reported when the block is not structurally present — R010 is already telling that
repo to install it, and the version of a missing block is not the news.

Plan output follows suit: for a stale or unmarked file with no missing sections, the plan
states what to regenerate instead of `No changes required.`, and says to replace the sections
in place rather than append (appending would duplicate them). Reporting "no changes" on a
stale block is precisely how it stayed stale.

**Bump `CANONICAL_BLOCK_VERSION` whenever `guidelines.en.md` changes in a way consumers need.**

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

### R020 Unverified claims in a feature doc (WARN)

A feature doc containing the marker `docs-first:unverified` is reported as
`FEATURE_DOC_UNVERIFIED` — **one aggregate `WARN` per feature**, with the occurrence count.

The marker exists for migration from legacy design docs. A dated spec drifts from the
implementation, so every claim copied out of one is a hypothesis until read against the code.
Recording that state is not enough on its own: an untracked marker ages quietly into truth,
which is exactly how the design doc came to lie. This rule keeps it visible until it is
resolved, and the finding clears when the last marker is removed.

`WARN`, never `BLOCKER`: blocking would force whole-feature verification before anything can
land, making incremental migration impossible.

The token is `docs-first:unverified`, the same family as `docs-first: skip` (R018), and
deliberately not bracketed — a `[bracketed]` token reads as a markdown link and as a template
placeholder.

### R019 Code exists, feature doc does not (BLOCKER / WARN)

Two instruments with very different precision, deliberately kept apart.

**Declared map (exact, `BLOCKER`).** `feature_map` in `.docs-first/config.yml` maps code path
to feature slug. A mapped path that exists on disk with no matching `docs/features/<slug>/`
is `FEATURE_DOC_MISSING`: the repository itself asserted that mapping, so there is nothing to
infer. Entries are flat `path=slug` strings, not a nested mapping — the config parser must
stay trivial because the pre-commit hook and CI read it with bare `python3`, no PyYAML.

```yaml
feature_map: [src/voice=voice-transcription, src/tree=file-tree]
```

**Coverage ratio (heuristic, `WARN`).** `FEATURE_DOC_COVERAGE_LOW`, **one aggregate finding**,
never one per directory. Candidate code units are the immediate subdirectories of each code
root (`code_roots`, else the first existing of `src`, `lib`, `app`, `apps`, `packages`,
`internal`, `pkg`, `cmd`), minus build/dependency/test buckets and minus anything the declared
map already covers. Slug matching folds naming conventions, so `voiceTranscription` matches
`voice-transcription`.

The finding message states plainly that this is a **smell signal, not a measurement**:
candidates are directories, and a layered architecture has directories per layer, not per
feature. Per-directory findings would mark nearly every folder in such a repo and train the
reader to ignore the audit; the declared map is the precise instrument.

`coverage_min` (default **50**) sets the threshold. That default is a heuristic, not a
calibrated number — it exists so the rule says something in a repository that configured
nothing, which is the case it was built for. `coverage_gate: true` promotes the finding to
`BLOCKER`; without it the ratio never fails a gate.

Alignment mode only: in bootstrap there are no docs yet, so "coverage is low" is noise. A
repo with no recognizable code root produces no finding.

Malformed `feature_map` entries and a `coverage_min` outside 0–100 are reported as
`DOCS_FIRST_CONFIG_INVALID` (`WARN`).

### R018 Diff touches code but no feature doc (BLOCKER, opt-in via `--diff`)

Only runs when `--diff [BASE]` is passed (default base `origin/main`); the plain audit is
unchanged. The audit is otherwise blind to code, so a feature can ship fully implemented and
fully undocumented while every other rule passes. This is the cheap PR-time backstop:
`DIFF_CODE_WITHOUT_FEATURE_DOC` when the diff changes code files and nothing under
`docs/features/`.

The range is `BASE...HEAD` (three-dot) — what the branch contributes, not what landed on the
base meanwhile. `git diff`/`git log` are read-only, so this respects the planning-only
guardrail.

**What counts as code** is an extension allowlist (`DEFAULT_CODE_EXTENSIONS`), not
"everything that is not a doc": the latter flags a lockfile bump or a CI tweak as feature
work, and a rule that cries wolf on every chore is a rule people turn off. Override per repo
with `code_extensions` in `.docs-first/config.yml` (replaces the default set).

**Test paths are exempt by default** (`tests/`, `test/`, `spec/`, `*.test.*`, `*_test.*`,
…): a test-only change ships no behavior, and nothing is lost because a feature that ships
code *and* tests is still caught by its code files. `diff_exempt_globs` in the config
**extends** these defaults; it never replaces them.

**Escape hatch:** `docs-first: skip` anywhere in the range's commit messages (honored across
the whole range, not just `HEAD`, because in CI `HEAD` is often a merge commit whose message
nobody wrote).

An unresolvable base, or an unavailable `git`, is `DIFF_BASE_UNRESOLVED` (`WARN`) and the
check is skipped — never a `BLOCKER`, because failing a pipeline over a missing ref punishes
the wrong mistake. Note that `actions/checkout` clones shallow by default, which makes
`origin/main` unresolvable; the generated CI workflow therefore sets `fetch-depth: 0`.

### R017 Feature reachable from the index and the nav (BLOCKER)

Every directory under `docs/features/` must be reachable:

- linked from `docs/features/INDEX.md` — otherwise `FEATURE_NOT_IN_INDEX`;
- present in the `mkdocs.yml` nav — otherwise `FEATURE_NOT_IN_NAV`.

R008 already validates nav → file and R013 index → canonical docs; this is the missing
reverse direction. A feature the reader cannot find is undocumented in practice.

Detection is by resolved link target, so both `[x](slug/)` and `[x](slug/README.md)` count
(a folder link resolves to its `README.md`), as does a deep link to `flows.md`.

**Nav coverage is conditional.** It is only enforced when the nav already enumerates at
least one path under `features/`. Setups built on `mkdocs-awesome-pages` or `literate-nav`
never list files, and flagging every feature in such a repository would be a pure false
positive. Missing, unparseable, or unreadable `mkdocs.yml` produces no finding here — R008
and `MKDOCS_YAML_ERROR` already report those causes.

**Breaking change.** A repository that documented features without indexing them audits
green today and turns `BLOCKER` on upgrade.

### R016 Spec written outside `docs/features/` (WARN)

`docs/features/` is the single source of truth for feature behavior, so a design document
under an excluded design-doc subtree (`docs/superpowers/specs/`) is either pre-adoption
legacy or an agent that ignored the redirect in the canonical block. Presence is the
violation — there is no threshold to calibrate and no ratio to interpret.

Reported as **one aggregate `WARN` per subtree** (`SPEC_OUTSIDE_FEATURE_DOCS`) with the
document count and up to five filenames: the resolution is identical for every file
(migrate what is still true into the feature docs, delete the rest), so one finding per
file would only drown the rest of the audit.

The finding persists until the folder is empty. That is deliberate — there is no
acknowledgement flag, because a permanent design-doc archive contradicts the model: a spec
is history that dies at merge. Note the audit *excludes* this subtree from every other rule
(see Evaluation Scope) while still counting it here: the folder is not audited as
documentation, but its contents are evidence about the gap in `docs/features/`.

## Classification Rules

Use strict immediate alignment defaults:

- Required file missing => `BLOCKER`
- AI instruction workflow/principles section missing => `BLOCKER`
- Workflow section not referencing `docs/features/` => `BLOCKER`
- Installed canonical block older than the skill's => `WARN`; unmarked or newer => `INFO`
- Feature README section missing from the majority => `WARN`
- Design document present outside `docs/features/` => `WARN`
- Broken traceability => `BLOCKER`
- Broken links or nav references => `BLOCKER`
- Feature folder unreachable from `features/INDEX.md` or the nav => `BLOCKER`
- In `--diff` mode, code changed with no feature doc touched => `BLOCKER`; unresolvable diff
  base => `WARN`
- Mapped code path with no feature doc => `BLOCKER`; low coverage ratio => `WARN`
  (`BLOCKER` only when `coverage_gate: true`)
- Feature doc carrying `docs-first:unverified` markers => `WARN`
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

### Legacy Spec Migration

When design documents exist with no corresponding feature doc, the plan adds a
`Legacy Spec Migration` subsection under the alignment plan: one row per design doc with a
candidate slug (derived from the filename, minus a leading date and a `-design` suffix) and
the four target files.

**Structure only — never a create diff.** The content must come from reading the
implementation, not from the design doc: a dated spec drifts, so transcribing it would
launder stale claims into the source of truth. All four targets therefore land in deferred
creation with that reason, which is the same guardrail that blocks placeholder scaffolding.

The rendered procedure is: read the code → write the four files from what the code does →
mark anything unconfirmed with `docs-first:unverified` (R020) → link the feature from
`INDEX.md` and the nav (R017) → delete the design doc, clearing `SPEC_OUTSIDE_FEATURE_DOCS`
(R016). Specs whose candidate slug already has a feature doc are skipped, folding naming
conventions.

## Non-Mutation Constraint

The compliance scripts and skill execution must not:

- edit files
- run formatters in write mode
- run code generation that mutates tracked files
- run migration commands

Read-only inspection commands are allowed, including the `git diff`/`git log`/`git rev-parse`
calls that back `--diff` mode.

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

When `.docs-first/config.yml` is present, unknown profile keys, unknown enforcement-gate keys,
malformed `feature_map` entries (not `path=slug`) and a `coverage_min` outside 0–100 are
reported as `DOCS_FIRST_CONFIG_INVALID` (`WARN`). Absent file is never a finding.

Recognized keys: `version`, `profiles`, `enforcement_chosen`, `enforcement_declined`,
`snapshot_declined`, `diff_exempt_globs`, `code_extensions`, `feature_map`, `code_roots`,
`coverage_gate`, `coverage_min`, `updated`. Values stay inside a flat subset of YAML
(scalars and inline lists of bare tokens) so the gate can parse the file without PyYAML;
this is why `feature_map` uses `path=slug` strings instead of nesting.

### Enforcement reconciliation

The audit compares `.docs-first/config.yml` `enforcement_chosen` against installed gate artifacts
(`.github/workflows/docs-audit.yml`, `.githooks/pre-commit`, `.claude/settings.json` with a `hooks`
key, `.codex/hooks.json`):

- A chosen gate with no artifact on disk => `ENFORCEMENT_GATE_MISSING` (`WARN`).
- No gate chosen and none present, in a docs repo (alignment mode) => `NO_ENFORCEMENT_GATE` (`INFO`).

Enforcement is never a `BLOCKER`: the skill never forces a gate.
