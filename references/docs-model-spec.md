# Canonical Documentation Model

## Purpose

Define the strict baseline documentation model that this skill enforces for bootstrap and alignment planning.

## Canonical Required Files

### Root-level required files

- `mkdocs.yml`
- `docs/requirements-mkdocs.txt`
- `docs/index.md`
- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/GLOSSARY.md`
- `docs/DECISIONS.md`
- `docs/ROADMAP.md`
- `docs/BACKLOG.md`
- `docs/nfr/NON_FUNCTIONAL.md`
- `docs/features/INDEX.md`
- `docs/reports/README.md`

### Feature-level required files

For each directory under `docs/features/<feature>/`:

- `README.md`
- `flows.md`
- `rules.md`
- `notes.md`

## Feature README Minimum Sections

Each `docs/features/<feature>/README.md` must include:

- `## Visao Geral`
- `## Requisitos (REQ-*)`
- `## Criterios de Aceite (AC-*)`
- `## Dependencias`
- `## Rastreabilidade`
- `## Nao Escopo`
- `## Questoes em Aberto`

## ID Conventions

- Functional requirement: `REQ-<FEATURE>-NNN`
- Acceptance criterion: `AC-<FEATURE>-NNN`
- Non-functional requirement: `NFR-NNN`
- Non-functional acceptance criterion: `AC-NFR-NNN`

Where:

- `<FEATURE>` uses uppercase letters, digits, and `-`
- `NNN` is zero-padded, three digits

## Traceability Rules

- Every AC heading in feature README must reference at least one `REQ-*` in the same file.
- Every AC-NFR heading in `docs/nfr/NON_FUNCTIONAL.md` must reference at least one `NFR-*` in the same file.
- Internal markdown links must resolve to existing files.
- `mkdocs.yml` nav markdown references must resolve to existing files under `docs/`.

## Non-canonical Artifacts To Ignore

- `.DS_Store`
- `.obsidian/`
- editor-specific metadata
- OS cache files

## Output Contract

The planning output must always include:

1. `Resumo Executivo`
2. `Matriz de Aderencia (BLOCKER/WARN/INFO)`
3. `Plano de Adequacao Imediata`
4. `Lista de arquivos a criar/alterar`
5. `Diffs propostos (sem aplicar)`

## Severity Guidelines

- `BLOCKER`: required structure/rule not satisfied.
- `WARN`: non-blocking quality issue.
- `INFO`: contextual guidance.
