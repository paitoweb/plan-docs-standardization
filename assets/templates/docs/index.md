# {{PROJECT_NAME}} - Documentation

Product and engineering documentation for the project.

---

## Documentation Map

What each document and folder is for — and what does **not** belong in it.

| Document / Folder | Answers | Granularity | Cadence | Do not put here |
|---|---|---|---|---|
| This page (`index.md`) | "Where do I start / what is each doc?" | Navigation | When the structure changes | Product content |
| [Project Brief](PROJECT_BRIEF.md) | "Why does this exist, for whom?" | Vision / goal | Rarely | Requirements, technical detail |
| [Architecture](ARCHITECTURE.md) | "How is the system structured?" | Components / data | When the architecture changes | Operational state, backlog |
| [Glossary](GLOSSARY.md) | "What does this term mean?" | Domain term | When a term appears | — |
| [Decisions (ADR)](DECISIONS.md) | "Why did we decide this?" | Decision | Append per decision | Current status, plans |
| [Roadmap](ROADMAP.md) | "What is the strategy and which phase?" | Phase / milestone | When a phase changes state | Live state, changelog |
| [Backlog](BACKLOG.md) | "What is queued and at what priority?" | Item (P0/P1/P2) | When an item is born / delivered | Branch / PR / deploy state |
| [NFR](nfr/NON_FUNCTIONAL.md) | "Which non-functional requirements and ACs?" | NFR / AC-NFR | When an NFR changes | — |
| [Features](features/INDEX.md) | "Requirements, flows, rules, notes per feature" | REQ / AC per feature | When the feature evolves | Operational state |
| [Reports](reports/README.md) | "What was verified/investigated + where we are now" | Report / snapshot | Reports: per event · `CURRENT_STATE`: per session | Design truth |

> **Boundary rule.** Operational session-state — current branch, open/merged PR, deploy
> version per environment, the next physical action, the last session's narrative — is
> **not design truth**. It never goes in `ROADMAP.md`, `BACKLOG.md`, or `DECISIONS.md`.
> Narrative history lives in git history and PR descriptions. To track live state, use the
> optional snapshot `reports/CURRENT_STATE.md` (rewritten each session, never append-only).
