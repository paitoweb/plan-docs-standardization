## Workflow: New Feature

Steps in order — each typically corresponds to one interaction. Steps may be combined when the feature is small.

**IMPORTANT**: Before advancing to any step, verify that the previous ones were completed. If the user asks to implement without docs, requirements, and a plan in place, question it and guide them back to the correct step.

1. **Brainstorm** — align intent and technical choices with the user (skill `superpowers:brainstorming` or similar; using a skill is optional).
2. **Spec** — create the feature structure under `docs/features/<feature>/` (if it does not exist) and write it with concrete REQs/ACs.
3. **Plan** — analyze the documentation and create an implementation plan (skill `superpowers:writing-plans` or similar; using a skill is optional).
4. **Review** — review and approve the plan with the user.
5. **Implementation** — implement the approved plan, using TDD when applicable.
6. **Document** — update `ROADMAP.md` and `BACKLOG.md` if it makes sense, `DECISIONS.md` and `ARCHITECTURE.md` if the decision is architectural, any other documents needed based on the completed implementation, and whatever the feature needs under `docs/features/<feature>/`.
7. **Tests** — create/update tests (following the traceability principle) and validate (define the method/stack with the user).
8. **Commit & PR** — commit following the conventions and open a PR referencing REQ-AC and linking to the feature doc (`docs/features/<feature>/`).

## Working Principles

They complement the project's "non-negotiable invariants" and "NOT list". They are stances, not technical rules:

- **Clarify before implementing**: when in doubt, ask — never assume product requirements, technical requirements, engineering principles, or hard constraints.
- **Distinguish assumption from fact**: make explicit when something is your own conclusion, a hypothesis, or an assumption vs. established project data/rule.
- **Official docs for APIs**: for libraries and SDKs, rely only on official documentation — never assume signatures, methods, or behaviors.
- **Pragmatism**: be practical and direct. Do not invent out-of-scope features. Do not ramble.
- **traceability**: traceability is mandatory at three ends: documented requirement (`REQ-*` under `docs/features/`), **source code that implements a REQ cites the ID** (function/constant JSDoc or file header), and tests include a `// Traceability:` comment pointing to the doc.

## Documentation Map

Before writing or updating documentation, consult the map in [docs/index.md](docs/index.md) to find the right home for the content.

- **Feature work** → `docs/features/<feature>/` (README, flows, rules, notes).
- **Architectural decision** → `docs/DECISIONS.md` (ADR).
- **Strategy / phase** → `docs/ROADMAP.md`. **Queue / priority** → `docs/BACKLOG.md`.
- **Operational session-state** (branch, PR, deploy version, next action, last-session narrative) never goes in the plan docs. To track it, use the optional snapshot `docs/reports/CURRENT_STATE.md` — rewritten each session, never append-only. Narrative history lives in git and PR descriptions.
- **Do not invent new top-level docs.** If something has no home in the map, propose adding it to the map first.
