## Workflow: New Feature

Steps in order — each typically corresponds to one interaction. Steps may be combined when the feature is small.

**IMPORTANT**: Before advancing to any step, verify that the previous ones were completed. If the user asks to implement without docs, requirements, and a plan in place, question it and guide them back to the correct step.

**IMPORTANT — where the spec goes. This project's preference overrides any skill default.** If you use a design/brainstorming skill (e.g. `superpowers:brainstorming`), write its spec to `docs/features/<feature>/` in this project's format — **never** to `docs/superpowers/specs/` or any other dated design-doc path. Skills that document a default spec location defer to this preference. Only the *implementation plan* may live in a process folder (e.g. `docs/superpowers/plans/`): a plan is the step sequence of one execution — history, and it dies at merge.

`docs/features/` is the **single source of truth** for feature behavior. A design doc outside it is not documentation: never read `docs/superpowers/specs/` (or any equivalent) as current behavior, and never treat "I wrote a spec" as "the feature is documented". When a design doc and a feature doc disagree, the feature doc is right and the design doc is stale.

1. **Brainstorm** — align intent and technical choices with the user (skill `superpowers:brainstorming` or similar; using a skill is optional).
2. **Feature doc — this *is* the spec** — create the feature structure under `docs/features/<feature>/` (if it does not exist) and write it with concrete REQs/ACs. To place a brainstorm's output, use the mapping table in the Documentation Map below.
3. **Plan** — analyze the documentation and create an implementation plan (skill `superpowers:writing-plans` or similar; using a skill is optional).
4. **Review** — review and approve the plan with the user.
5. **Implementation** — implement the approved plan, using TDD when applicable.
6. **Document** — update `ROADMAP.md` and `BACKLOG.md` if it makes sense, `DECISIONS.md` and `ARCHITECTURE.md` if the decision is architectural, any other documents needed based on the completed implementation, and whatever the feature needs under `docs/features/<feature>/`.
7. **Tests** — create/update tests (following the traceability principle) and validate (define the method/stack with the user).
8. **Commit & PR** — commit following the conventions and open a PR referencing REQ-AC and linking to the feature doc (`docs/features/<feature>/`). If you keep the local snapshot `docs/reports/CURRENT_STATE.md` (gitignored — never committed), update it with where things stand and the next action.

## Working Principles

They complement the project's "non-negotiable invariants" and "NOT list". They are stances, not technical rules:

- **Clarify before implementing**: when in doubt, ask — never assume product requirements, technical requirements, engineering principles, or hard constraints.
- **Distinguish assumption from fact**: make explicit when something is your own conclusion, a hypothesis, or an assumption vs. established project data/rule.
- **Official docs for APIs**: for libraries and SDKs, rely only on official documentation — never assume signatures, methods, or behaviors.
- **Pragmatism**: be practical and direct. Do not invent out-of-scope features. Do not ramble.
- **traceability**: traceability is mandatory at three ends: documented requirement (`REQ-*` under `docs/features/`), **source code that implements a REQ cites the ID** (function/constant JSDoc or file header), and tests include a `// Traceability:` comment pointing to the doc.

## Documentation Map

Before writing or updating documentation, consult the map in [docs/index.md](docs/index.md) to find the right home for the content.

- **Feature work** → `docs/features/<feature>/` (README, flows, rules, notes). This is the only place a feature's behavior is documented.
- **Brainstorm output → feature doc.** Do not write a standalone design document. Split the design across the canonical files:

  | Design output | Destination |
  |---|---|
  | purpose, scope | `README.md` → overview |
  | requirements | `README.md` → `REQ-<FEATURE>-NNN` |
  | success criteria | `README.md` → `AC-<FEATURE>-NNN` (each citing its REQ) |
  | architecture, data flow | `flows.md` |
  | rules, invariants, error handling | `rules.md` |
  | trade-offs, rejected alternatives, open questions | `notes.md` |
  | architectural decision | `docs/DECISIONS.md` (ADR) |

- **Architectural decision** → `docs/DECISIONS.md` (ADR).
- **Strategy / phase** → `docs/ROADMAP.md`. **Queue / priority** → `docs/BACKLOG.md`.
- **Operational session-state** (branch, PR, deploy version, next action, last-session narrative) never goes in `docs/ROADMAP.md`, `docs/BACKLOG.md`, or `docs/DECISIONS.md`. To track it, use the optional **local, gitignored** snapshot `docs/reports/CURRENT_STATE.md` — never committed, rewritten freely each session. Versioned history lives in git and PR descriptions. When the user asks where the project stands or what the next steps are, consult `docs/reports/CURRENT_STATE.md` first (if it exists) before answering.
- **Do not invent new top-level docs.** If something has no home in the map, propose adding it to the map first.
