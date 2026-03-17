# Indice de Features

Ultima atualizacao: {{LAST_UPDATED}}

## Proposito
Centralizar navegacao das features com rastreabilidade para requisitos e criterios.

## Padrao de IDs

- Requisito funcional: `REQ-<FEATURE>-NNN`
- Criterio de aceite: `AC-<FEATURE>-NNN`
- Requisito nao funcional: `NFR-NNN`

## Catalogo de Features

| Feature | Prioridade | Status | Pasta | Fluxos | Regras |
|---|---|---|---|---|---|
| [Nome da feature] | P0 | Ativo | [`feature-slug/`](feature-slug/README.md) | [flows.md](feature-slug/flows.md) | [rules.md](feature-slug/rules.md) |

## Requisitos Nao Funcionais

- Documento global: [`../nfr/NON_FUNCTIONAL.md`](../nfr/NON_FUNCTIONAL.md)

## Relatorios

- [Indice de relatorios](../reports/README.md)

## Regras de Governanca

- Toda feature DEVE possuir `README.md`, `flows.md`, `rules.md`, `notes.md`.
- Todo requisito funcional DEVE receber ID `REQ-*` unico.
- Todo criterio de aceite DEVE receber ID `AC-*` e referenciar ao menos um `REQ-*`.
- Todo requisito transversal DEVE ser registrado em `docs/nfr/NON_FUNCTIONAL.md`.
- Termos de dominio DEVEM ser definidos em [`../GLOSSARY.md`](../GLOSSARY.md).
