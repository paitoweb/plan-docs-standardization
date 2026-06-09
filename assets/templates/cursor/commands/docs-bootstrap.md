# Docs Bootstrap

Bootstrap the canonical documentation structure for this project using the Docs-First method.

## Instructions

1. Read and follow the `plan-docs-standardization` skill at `.cursor/skills/plan-docs-standardization/SKILL.md`.
2. Detect mode: this is **bootstrap** if `docs/` does not exist.
3. Inspect the repository (read-only) to understand the project name, stack, and purpose.
4. Produce the required planning output (do **not** mutate files unless the user explicitly asks to apply the plan):
   - Executive Summary
   - Compliance Matrix (BLOCKER/WARN/INFO)
   - Immediate Alignment Plan
   - File Create/Alter List
   - Proposed Diffs (not applied)
5. Use templates from `.resources/plan-docs-standardization/assets/templates/` when proposing missing files.
6. Replace template tokens: `{{PROJECT_NAME}}`, `{{FEATURE_NAME}}`, `{{FEATURE_ID}}`, `{{LAST_UPDATED}}`.
7. Do not emit placeholder-only scaffolds — defer creation with reason when concrete content is unavailable.

If the user provides a project description in this message, use it to populate PROJECT_BRIEF and initial feature docs in the proposed diffs.
