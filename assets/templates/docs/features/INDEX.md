# Feature Index

Last updated: {{LAST_UPDATED}}

## Purpose
Centralize feature navigation with traceability to requirements and criteria.

## ID Conventions

- Functional requirement: `REQ-<FEATURE>-NNN`
- Acceptance criterion: `AC-<FEATURE>-NNN`
- Non-functional requirement: `NFR-NNN`

## Feature Catalog

| Feature | Priority | Status | Folder | Flows | Rules |
|---|---|---|---|---|---|
| [Feature name] | P0 | Active | [`feature-slug/`](feature-slug/README.md) | [flows.md](feature-slug/flows.md) | [rules.md](feature-slug/rules.md) |

## Non-Functional Requirements

- Global document: [`../nfr/NON_FUNCTIONAL.md`](../nfr/NON_FUNCTIONAL.md)

## Reports

- [Report index](../reports/README.md)

## Governance Rules

- Every feature MUST have `README.md`, `flows.md`, `rules.md`, `notes.md`.
- Every functional requirement MUST receive a unique `REQ-*` ID.
- Every acceptance criterion MUST receive an `AC-*` ID and reference at least one `REQ-*`.
- Every cross-cutting requirement MUST be registered in `docs/nfr/NON_FUNCTIONAL.md`.
- Domain terms MUST be defined in [`../GLOSSARY.md`](../GLOSSARY.md).
