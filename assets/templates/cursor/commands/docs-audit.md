# Docs Audit

Audit Docs-First compliance (documentation model **and** code/test traceability) and produce a non-mutating alignment plan when needed.

## Instructions

1. Read and follow the `plan-docs-standardization` skill at `.cursor/skills/plan-docs-standardization/SKILL.md`.
2. Run the audit script (read-only). This single command checks docs structure, REQ/AC traceability, links, mkdocs nav, AI rules, **and** code/test traceability via `docs/traceability.json`:

```bash
python3 .resources/plan-docs-standardization/scripts/audit_docs_model.py .
```

Optional JSON output for tooling:

```bash
python3 .resources/plan-docs-standardization/scripts/audit_docs_model.py . --format json
```

3. Run the alignment plan builder (read-only) when findings need remediation proposals:

```bash
python3 .resources/plan-docs-standardization/scripts/build_docs_alignment_plan.py .
```

4. Synthesize script output into the required sections:
   - Executive Summary
   - Compliance Matrix (BLOCKER/WARN/INFO)
   - Immediate Alignment Plan
   - File Create/Alter List
   - Proposed Diffs (not applied)
5. Do **not** edit, create, or delete any repository files unless the user explicitly asks to apply the plan.

Before marking implementation work complete, re-run step 2 and confirm **0 BLOCKERs**.

If `.resources/plan-docs-standardization` is missing, report that the symlink must be created (see `.cursor/README.md`).
