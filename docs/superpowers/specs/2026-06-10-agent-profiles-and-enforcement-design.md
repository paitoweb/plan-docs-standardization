# Design — Per-Agent Profiles & Enforcement Gates

- **Date:** 2026-06-10
- **Status:** Draft (for review)
- **Skill:** `plan-docs-standardization`
- **Supersedes:** the closed PR #4 ("Add Cursor IDE support") — this is a clean redesign from `main` (post-#5).

## 1. Context & Motivation

The skill standardizes documentation using one canonical docs model (MkDocs + `docs/` tree, REQ/AC/NFR traceability). Today it is implicitly Claude-Code-shaped: the "AI-instruction" alignment targets a flat list of files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`) and proposes one canonical block.

We want the skill to **serve multiple AI coding agents as first-class targets** — Claude Code, Cursor, and OpenAI Codex CLI — while keeping the method itself **single and agent-agnostic**. The closed PR #4 attempted Cursor support by forking content (a hand-written rule + a copied `SKILL.md`), which immediately drifted from the canonical block and coupled in an unrelated code-traceability feature. The lesson: **per-agent variation must be a thin, declarative adapter over a single source — never a fork of content.**

A second, equally important motivation surfaced during design: the real goal is not just *where* instructions live, but **how to make the Docs-First method binding implementation-by-implementation**. Instructions of any kind are *soft* (they shape the model but it can drift). True enforcement is a *deterministic gate outside the model*. The skill must offer both layers, without ever forcing them on the user.

## 2. Goals / Non-Goals

### Goals
- One agnostic method + docs model, authored once, serving all supported agents.
- A declarative **agent profile** abstraction that customizes **delivery only** (where/how instructions and skills are installed, which enforcement primitives exist).
- Support **multiple active profiles in one repo** (e.g. `.claude/` + `.cursor/` together).
- **Detect** the active agent(s); if undetectable, **ask**; **persist** the decision so re-runs do not re-ask.
- Offer a **soft layer** (strongest always-on instruction per agent) and an optional **hard layer** (deterministic audit gate), the latter under an explicit, never-forced consent model.
- Preserve the skill's read-only/planning nature: nothing mutates without explicit, previewed consent.
- Enforce single-source with **anti-drift tests** so per-agent artifacts cannot silently diverge from canonical content.

### Non-Goals
- **Code traceability** (`docs/traceability.json`, REQ-in-source / `Traceability:`-in-test gates) — valuable but orthogonal; a separate, agent-agnostic PR.
- The `.resources/` symlink convention from PR #4 — dead; native per-agent install replaces it.
- Per-agent variation of the *method* or the `docs/` tree — out of bounds by design (see §4 guardrail).
- Supporting ChatGPT (web product) as a skill *runtime* — it has none; it is an output-only target.

## 3. The Hard Guardrail (most important constraint)

> **A profile customizes *delivery*, never the *method*.** The `docs/` tree, the REQ/AC/NFR model, the workflow + working-principles text, and the audit logic are identical for every agent. A profile may only change: which instruction file carries the always-on block, its file format/wrapper, where the skill package is installed, and which enforcement primitives are available. The moment a per-agent "optimization" would change `docs/` structure or the traceability model, it is core — not a profile — and is rejected.

This keeps "one method, many agents" true and prevents the slow slide into N methods.

## 4. Architecture — Generic Core + Declarative Profile Overlays

```
Canonical (single source, agnostic)
  ├─ docs/ tree templates (PROJECT_BRIEF, ARCHITECTURE, GLOSSARY, DECISIONS,
  │   ROADMAP, BACKLOG, nfr/, features/, reports/, index.md map)
  ├─ assets/templates/ai-instructions/guidelines.en.md   (workflow + principles + map pointer)
  ├─ SKILL.md + references/                               (the method)
  └─ scripts/audit_docs_model.py, build_docs_alignment_plan.py

Profiles (thin, declarative — adapters only)
  ├─ claude   → soft: CLAUDE.md;                  skill: .claude/skills/;  hard: Claude Code hooks
  ├─ cursor   → soft: .cursor/rules/*.mdc (alwaysApply); skill: .cursor/skills/; hard: git/CI only
  ├─ codex    → soft: AGENTS.md (≤32 KiB);        skill: .agents/skills/;  hard: Codex hooks
  └─ generic  → soft: AGENTS.md;                  skill: (none);           hard: git/CI only

Composition:  delivery(agent) = canonical_block ⊕ profile_overlay
```

Every overlay artifact is **generated from canonical sources** at install/plan time. Hand-written per-agent prose is forbidden; an anti-drift test asserts each generated artifact equals `generate(canonical)`.

### 4.1 What a profile declares (data, not prose)

A profile is a small manifest with:
- `soft_target` — path + optional wrapper for the always-on instruction block.
  - claude: `CLAUDE.md`, no wrapper.
  - cursor: `.cursor/rules/docs-first.mdc`, wrapper = `.mdc` frontmatter (`alwaysApply: true`, `description`).
  - codex: `AGENTS.md`, no wrapper, **lean variant** (32 KiB budget across the whole AGENTS chain).
  - generic: `AGENTS.md`, no wrapper.
- `skill_install` — where the skill package is copied/generated, if the agent hosts skills.
  - claude: `.claude/skills/plan-docs-standardization/`
  - cursor: `.cursor/skills/plan-docs-standardization/` (Cursor also reads `.claude/skills/`, but we install natively for clarity).
  - codex: `.agents/skills/plan-docs-standardization/` (Codex does **not** read `.claude/skills/`; path may have migrated — verify against installed CLI version).
  - generic: none.
- `native_hard_gate` — the agent's own blocking primitive, if any.
  - claude: Claude Code hooks in `.claude/settings.json` (`PreToolUse` block / `Stop` audit).
  - codex: Codex hooks in `<repo>/.codex/hooks.json` (`PreToolUse` → `permissionDecision: "deny"`; `Stop` re-prompts, does not hard-block).
  - cursor: none documented → relies on the agnostic gate.
  - generic: none.
- `detect_signals` — filesystem markers that imply this agent is in use (`.claude/`, `.cursor/`, `.codex/` or `.agents/skills/` or `AGENTS.md`).

Adding a new agent (Windsurf, Cline, Pulsar…) = one manifest entry (+ optional small overlay). No core change.

## 5. Agent Detection & State Persistence

### 5.1 Detection hierarchy (never rely on model self-introspection)
1. **Persisted config** — read `.docs-first/config.yml` `profiles:` if present. Authoritative.
2. **Environment signals** — filesystem markers (`.claude/`, `.cursor/`, `.codex/`, `AGENTS.md`).
3. **Ask the user** — only when 1 and 2 are inconclusive; then offer to persist.

Rationale: LLMs are unreliable at "which model am I"; the harness/filesystem and an explicit recorded decision are reliable.

### 5.2 The state file — `.docs-first/config.yml`

Stores **decisions, not observations** (anything derivable from the filesystem is re-derived, not stored):

```yaml
# .docs-first/config.yml
version: 1
profiles: [claude, cursor]        # which profiles the user WANTS active
enforcement:
  chosen:   [ci, local-hook]      # accepted gates
  declined: [claude-hooks]        # refused → never re-ask
updated: 2026-06-10
```

### 5.3 Lifecycle
- **Present** → read first; skip re-asking; audit accordingly.
- **Absent** → detect via signals; ask if ambiguous; **offer to create** it.
- **Stale** (new `.cursor/` appeared, user adds a profile) → **propose update**.
- **Writes only on consent.** A read-only audit run reads the file but never writes it. An in-run answer ("I use Cursor") is used for that run and *offered* for persistence — never written silently. This preserves the read-only guarantee.

### 5.4 Enforcement-drift reconciliation
Because the config records *intent* and the filesystem holds *reality*, the audit reconciles them:
- `chosen: [ci]` but no workflow file → `WARN` (`ENFORCEMENT_GATE_MISSING`).
- No gate chosen and none present → recurring `INFO` (`NO_ENFORCEMENT_GATE`), never a BLOCKER (honors "never force").

## 6. Soft Layer — Strongest Always-On Instruction Per Agent

The same canonical block (`guidelines.en.md`: workflow + working principles + `## Documentation Map` pointer) is delivered through each agent's strongest always-applied surface:

| Agent | Surface | Notes |
|---|---|---|
| Claude Code | `CLAUDE.md` | auto-loaded each session |
| Cursor | `.cursor/rules/docs-first.mdc` (`alwaysApply: true`) | committed; keep < 500 lines |
| Codex CLI | `AGENTS.md` (root) | always injected; 32 KiB chain budget → lean variant, detail in the skill |
| generic | `AGENTS.md` | broadly read by multiple tools |

Existing files are aligned **structurally** (workflow = numbered list, principles = bulleted list, map pointer = link to `docs/index.md`) — language-agnostic, never created without consent (absent → INFO).

## 7. Hard Layer — Deterministic Enforcement Gates (all optional)

All gates run the same `audit_docs_model.py`; they differ only in *where* the audit fires. None is forced.

### 7.1 The three gate locations
1. **CI + branch protection** (the real, unbypassable gate) — generated `.github/workflows/docs-audit.yml`; branch protection enabled so the check must pass before merge. Team-wide, zero per-dev setup. Branch protection is a *repo setting*, not a file → "do it for you" means a `gh api` call needing admin/auth.
2. **Local `pre-commit` via `core.hooksPath`** (shift-left speed bump) — committed `.githooks/pre-commit` + one-time `git config core.hooksPath .githooks`. Zero extra dependency (git + python3). Bypassable with `--no-verify`.
3. **Native agent hard gate (bonus)** — Claude Code hooks (`.claude/settings.json`) and Codex hooks (`.codex/hooks.json`, `PreToolUse` → `deny`). In-session, fastest feedback. Cursor: none → relies on (1)/(2).

### 7.2 Consent model (never force; warn; ask with a recommendation; install on consent)
1. **Never obligate** any gate.
2. **Warn, concretely**, what non-adoption risks:
   - *No gate*: the model degrades silently — code drifts from docs, REQ/AC traceability rots, docs eventually lie.
   - *Soft-only*: works until pressure (big PR, deadline) — i.e. fails when most needed.
   - *Local-hook-only*: bypassable; a teammate who didn't install it commits non-compliant code.
3. **Ask which to adopt, leading with a recommendation** (default stack: CI + branch protection, plus the local hook; native hooks where the agent offers them).
4. **Instruct + offer to do it**, with an explicit **preview** of every file write / config change / `gh api` call before acting (these touch `.git`, `settings.json`, `.github/`, `.codex/` — more sensitive than docs, so consent is per-action, not "apply all").

### 7.3 Gate granularity
The audit runs over the **repo state at commit/PR time**: each change must leave the repo compliant (no new BLOCKERs). A future optimization may scope to changed files; whole-repo is the simpler, stricter default.

## 8. Runtime Model — Hosts vs Output-Only Targets

- The skill is **authored once** (the method in markdown + scripts) and runs under any **skill-hosting runtime**: Claude Code, Cursor (native skills since v2.4), and Codex CLI (native skills in `.agents/skills/`).
- It **generates** the per-target artifacts (soft instruction file, skill package, chosen gates).
- For targets with **no skill runtime** (ChatGPT web), the skill only *generates* the static structure (`AGENTS.md` + `docs/`) — there is no in-session skill.
- No single skills directory serves all three runtimes (Cursor reads `.claude/skills/`; Codex reads only `.agents/skills/`), so each host gets a native install — confirming the per-target approach over a shared package.

## 9. Single-Source & Anti-Drift (decided: generator by script)

- All overlay artifacts (the Cursor `.mdc`, each soft-instruction variant, the skill package copies) are **generated** from `guidelines.en.md` / `SKILL.md` / templates — **never hand-maintained**. This is the chosen approach (DRY): canonical sources are the only place content is edited.
- A **generator script** — `scripts/render_profile_artifacts.py` — composes `profile_overlay ⊕ canonical` and emits each artifact. It is the single command a maintainer runs after editing canonical sources, and the same composition the plan/install path uses to propose per-agent files.
- Committed per-agent artifacts are the generator's output. **Tests** assert each committed artifact equals `render_profile_artifacts` output → editing a canonical source (or a profile manifest) without regenerating fails CI. This is the structural fix for the PR #4 drift class.

## 10. Testing Strategy

- Profile registry: each profile resolves to correct soft target / skill path / native gate.
- Detection: config present → no prompt; signals only → correct inference; ambiguous → asks.
- Multi-profile: `.claude/` + `.cursor/` → both overlays composed; config `profiles` is a list.
- Anti-drift: generated artifacts == canonical (the regression guard).
- Enforcement reconciliation: `chosen` vs filesystem → correct WARN/INFO; never BLOCKER.
- Consent/read-only: audit run never writes `.docs-first/config.yml` or any gate file.
- Existing 51 tests stay green (no regression to the agnostic core).

## 11. Out of Scope (explicit)
- Code traceability feature (separate PR).
- `.resources/` symlink (removed concept).
- Per-agent method/docs divergence (guardrail §3).
- ChatGPT-web as a runtime.

## 12. Open Questions / Risks
- **Codex skills path** (`.agents/skills/` per docs vs a legacy `~/.codex/skills/`) changed recently → installer should verify against the installed CLI version before writing.
- **Branch protection** cannot be delivered as a committed file; "do it for you" requires `gh api` + admin rights — must degrade gracefully when unavailable (generate workflow, instruct manual toggle).
- **AGENTS.md 32 KiB budget** shared across the whole chain → the Codex soft variant must stay lean; detailed procedure belongs in the skill, not the always-on file.
- **Cursor native hard gate**: none documented; if Cursor later ships hooks, add to its profile. Until then, Cursor enforcement = git/CI only (document this clearly).
