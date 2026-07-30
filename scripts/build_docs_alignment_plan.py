#!/usr/bin/env python3
"""Build strict, non-mutating docs alignment plans from audit findings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_docs_model as adm  # noqa: E402

SEVERITY_ORDER = {"BLOCKER": 0, "WARN": 1, "INFO": 2}

CREATE_CODES = {"MISSING_REQUIRED_FILE", "MISSING_FEATURE_FILE"}

IGNORE_ACTION_CODES = {"AI_INSTRUCTION_FILE_ABSENT"}

PLACEHOLDER_HINTS = (
    "[describe",
    "[item",
    "[title",
    "[question",
    "[dependency",
    "[segment",
    "[differentiator",
    "[objective",
    "[kpi",
    "[slo",
    "[out of scope",
    "[assumption",
    "[risk",
    "[definition",
    "[term",
    "[module",
    "[component",
    "[observation",
    "[context]",
    "[event]",
    "[expected result]",
    "given [",
    "when [",
    "then [",
)
PLACEHOLDER_BRACKET_RE = re.compile(r"\[[^\]\n]{2,120}\](?!\()")


def slug_to_feature_name(slug: str) -> str:
    parts = [segment for segment in slug.split("-") if segment]
    return " ".join(part.capitalize() for part in parts) or slug


def slug_to_feature_id(slug: str) -> str:
    value = re.sub(r"[^A-Z0-9]+", "-", slug.upper())
    return value.strip("-") or "FEATURE"


def skill_root() -> Path:
    return SCRIPT_DIR.parent


def templates_root() -> Path:
    return skill_root() / "assets" / "templates"


def target_to_template_path(target_rel: str) -> Path | None:
    templates = templates_root()
    target = Path(target_rel)

    if (
        len(target.parts) >= 4
        and target.parts[0] == "docs"
        and target.parts[1] == "features"
        and target.parts[-1] in set(adm.FEATURE_REQUIRED_FILES)
    ):
        return templates / "docs" / "features" / "_feature_" / target.parts[-1]

    candidate = templates / target_rel
    return candidate if candidate.exists() else None


def render_template(template_text: str, repo: Path, target_rel: str) -> str:
    target = Path(target_rel)
    project_name = repo.name
    feature_name = "Feature"
    feature_id = "FEATURE"

    if len(target.parts) >= 4 and target.parts[0] == "docs" and target.parts[1] == "features":
        slug = target.parts[2]
        feature_name = slug_to_feature_name(slug)
        feature_id = slug_to_feature_id(slug)

    rendered = template_text
    rendered = rendered.replace("{{PROJECT_NAME}}", project_name)
    rendered = rendered.replace("{{FEATURE_NAME}}", feature_name)
    rendered = rendered.replace("{{FEATURE_ID}}", feature_id)
    rendered = rendered.replace("{{LAST_UPDATED}}", str(date.today()))

    return rendered


def unified_add_diff(target_rel: str, content: str) -> str:
    lines = content.splitlines()
    hunk_count = len(lines)

    output = ["--- /dev/null", f"+++ b/{target_rel}", f"@@ -0,0 +1,{hunk_count} @@"]
    output.extend(f"+{line}" for line in lines)

    if content.endswith("\n"):
        return "\n".join(output) + "\n"
    return "\n".join(output)


def placeholder_update_diff(target_rel: str, reasons: list[str]) -> str:
    compact = "; ".join(reasons[:2])
    return "\n".join(
        [
            f"--- a/{target_rel}",
            f"+++ b/{target_rel}",
            "@@ PLAN @@",
            f"+# TODO(plan-docs-standardization): {compact}",
        ]
    )


def _append_block_diff(target_rel: str, file_lines: list[str], block_text: str, label: str | None = None) -> str:
    added: list[str] = [""]
    if label:
        added.append(label)
    added.extend(block_text.splitlines())
    start = len(file_lines)
    header = f"@@ -{start},0 +{start + 1},{len(added)} @@"
    body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
    body.extend(f"+{line}" for line in added)
    return "\n".join(body)


def feature_section_append_diff(repo: Path, target_rel: str, missing_titles: list[str]) -> str:
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    file_lines = text.splitlines()
    added: list[str] = []
    for title in missing_titles:
        added.extend(["", f"## {title}", ""])
    start = len(file_lines)
    header = f"@@ -{start},0 +{start + 1},{len(added)} @@"
    body = [f"--- a/{target_rel}", f"+++ b/{target_rel}", header]
    body.extend(f"+{line}" for line in added)
    return "\n".join(body)


def index_map_append_diff(repo: Path, target_rel: str) -> str:
    template = templates_root() / "docs" / "index.md"
    section = adm.extract_section(template.read_text(encoding="utf-8"), "## Documentation Map")
    if not section:
        return "# ERROR: canonical template missing '## Documentation Map' section."
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    return _append_block_diff(target_rel, text.splitlines(), section)


def ai_instruction_update_diff(repo: Path, target_rel: str) -> str:
    # Proposes the English canonical block as a labeled starting point for any
    # structurally-missing section. Human-facing; not intended for `git apply`.
    canonical = adm.load_canonical_sections()
    file_path = repo / target_rel
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    file_lines = text.splitlines()
    has_workflow, has_principles = adm.detect_ai_instruction_shapes(text)

    label = (
        "<!-- plan-docs-standardization: English starting point — "
        "translate to your project's language -->"
    )
    blocks: list[str] = []
    if not has_workflow:
        blocks.append(_append_block_diff(target_rel, file_lines, canonical["## Workflow: New Feature"], label))
    if not has_principles:
        blocks.append(_append_block_diff(target_rel, file_lines, canonical["## Working Principles"], label))
    if not adm.references_doc_index(file_path, repo):
        map_section = adm.load_canonical_map_section()
        if map_section:
            blocks.append(_append_block_diff(target_rel, file_lines, map_section, label))

    return "\n\n".join(blocks) if blocks else "No changes required."


def placeholder_marker_count(content: str) -> int:
    lowered = content.lower()
    count = sum(lowered.count(marker) for marker in PLACEHOLDER_HINTS)
    count += len(PLACEHOLDER_BRACKET_RE.findall(content))
    return count


def sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[int, str, int, str]:
        return (
            SEVERITY_ORDER.get(item.get("severity", "INFO"), 9),
            item.get("path", ""),
            item.get("line") or 0,
            item.get("code", ""),
        )

    return sorted(findings, key=key)


def collect_actions(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    create: set[str] = set()
    alter: set[str] = set()

    for finding in result["findings"]:
        path = finding["path"]
        code = finding["code"]

        if code in IGNORE_ACTION_CODES:
            continue
        if code in CREATE_CODES:
            create.add(path)
        else:
            alter.add(path)

    # Do not list files to alter when they are missing and will be created.
    alter -= create

    return sorted(create), sorted(alter)


def proposed_diffs(
    repo: Path,
    result: dict[str, Any],
    create_files: list[str],
    alter_files: list[str],
    max_diffs: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    items: list[dict[str, str]] = []
    deferred_create: list[dict[str, str]] = []

    grouped_reasons: dict[str, list[str]] = defaultdict(list)
    for finding in result["findings"]:
        grouped_reasons[finding["path"]].append(finding["message"])

    for target_rel in create_files:
        if len(items) >= max_diffs:
            break

        template_path = target_to_template_path(target_rel)
        if not template_path or not template_path.exists():
            deferred_create.append(
                {
                    "path": target_rel,
                    "reason": (
                        "Canonical template not found. Without a content base, creation diff was deferred."
                    ),
                }
            )
            continue

        template_text = template_path.read_text(encoding="utf-8")
        content = render_template(template_text, repo, target_rel)

        marker_count = placeholder_marker_count(content)
        if marker_count > 0:
            deferred_create.append(
                {
                    "path": target_rel,
                    "reason": (
                        "Template requires manual filling and would produce placeholders without an explicit "
                        "writing task/content. Creation deferred until concrete content is available."
                    ),
                }
            )
            continue

        items.append(
            {
                "path": target_rel,
                "type": "create",
                "diff": unified_add_diff(target_rel, content),
            }
        )

    ai_instruction_targets = set(adm.ai_instruction_targets(repo))
    feature_gaps = adm.compute_feature_section_gaps(repo)

    for target_rel in alter_files:
        if len(items) >= max_diffs:
            break
        if any(
            f["path"] == target_rel and f["code"] == "INDEX_MAP_MISSING"
            for f in result["findings"]
        ):
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": index_map_append_diff(repo, target_rel),
                }
            )
            continue
        if target_rel in ai_instruction_targets:
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": ai_instruction_update_diff(repo, target_rel),
                }
            )
            continue
        if target_rel in feature_gaps:
            items.append(
                {
                    "path": target_rel,
                    "type": "update",
                    "diff": feature_section_append_diff(repo, target_rel, feature_gaps[target_rel]),
                }
            )
            continue
        reasons = grouped_reasons.get(target_rel, ["Update to comply with the canonical model"])  # pragma: no cover
        items.append(
            {
                "path": target_rel,
                "type": "update-plan",
                "diff": placeholder_update_diff(target_rel, reasons),
            }
        )

    return items, deferred_create


def legacy_spec_migration(repo: Path) -> list[dict[str, Any]]:
    """One entry per legacy design doc with no feature doc yet.

    Deliberately proposes structure and no content. The spec is a *lead*: it says a feature
    exists and roughly what it was meant to do. The source of truth is the implementation --
    a dated design doc drifts from the code, so copying it into the feature doc would
    launder stale claims into the one place that must not lie. Content comes from reading
    the code, and each claim carries the unverified marker until it has been.
    """

    documented = {adm.normalize_slug(path.name) for path in adm.collect_feature_dirs(repo)}

    entries: list[dict[str, Any]] = []
    for prefix in adm.IGNORED_DOCS_SUBTREES:
        subtree = repo / prefix
        if not subtree.is_dir():
            continue
        for spec in sorted(subtree.rglob("*.md")):
            if adm.should_ignore_path(spec):
                continue
            slug = adm.spec_to_candidate_slug(spec.name)
            if adm.normalize_slug(slug) in documented:
                continue  # a feature doc for this slug already exists
            entries.append(
                {
                    "spec": spec.relative_to(repo).as_posix(),
                    "slug": slug,
                    "targets": [
                        f"docs/features/{slug}/{name}" for name in adm.FEATURE_REQUIRED_FILES
                    ],
                }
            )
    return entries


MIGRATION_DEFERRED_REASON = (
    "Legacy spec migration: structure proposed, content deferred. The content must be "
    "derived from the implementation, not copied from the dated design doc, which has "
    "likely drifted. Write each claim from the code and mark anything unconfirmed with "
    f"'{adm.UNVERIFIED_MARKER}'."
)


def build_markdown(
    repo: Path,
    result: dict[str, Any],
    create_files: list[str],
    alter_files: list[str],
    diffs: list[dict[str, str]],
    deferred_create: list[dict[str, str]],
    migration: list[dict[str, Any]] | None = None,
) -> str:
    migration = migration or []
    summary = result["summary"]
    findings = sort_findings(result["findings"])

    lines: list[str] = []

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- Repository: `{repo}`")
    lines.append(f"- Detected mode: `{result['mode']}`")
    lines.append(
        "- Result: "
        f"{summary['blocker']} BLOCKER, {summary['warn']} WARN, {summary['info']} INFO"
    )
    lines.append(
        "- Applied policy: strict immediate alignment (any required divergence = BLOCKER)."
    )
    lines.append("")

    lines.append("## Compliance Matrix (BLOCKER/WARN/INFO)")
    lines.append("")
    lines.append("| Severity | Code | File | Message |")
    lines.append("|---|---|---|---|")

    if not findings:
        lines.append("| INFO | CLEAN | - | No deviations found |")
    else:
        for finding in findings:
            location = finding["path"]
            if finding.get("line"):
                location = f"{location}:{finding['line']}"
            message = finding["message"].replace("|", "\\|")
            lines.append(
                f"| {finding['severity']} | {finding['code']} | `{location}` | {message} |"
            )

    lines.append("")
    lines.append("## Immediate Alignment Plan")
    lines.append("")
    lines.append("1. Create all required files missing from the canonical model.")
    lines.append(
        "2. Fix existing files with missing sections, ID format issues, and AC->REQ/AC-NFR->NFR traceability failures."
    )
    lines.append("3. Fix broken internal links and invalid mkdocs nav references.")
    lines.append("4. Re-run audit until BLOCKER count reaches zero.")
    lines.append("")

    if migration:
        lines.append("### Legacy Spec Migration (spec is the lead, code is the source)")
        lines.append("")
        lines.append(
            f"{len(migration)} design document(s) have no feature doc yet. Do **not** copy "
            "them across: a dated spec drifts from the implementation, so transcribing it "
            "would launder stale claims into the source of truth. Per feature, in order:"
        )
        lines.append("")
        lines.append(
            "1. Read the implementation. The spec only tells you the feature exists and "
            "roughly what it was meant to do."
        )
        lines.append(
            "2. Write `README.md` (overview, `REQ-*`, `AC-*` citing their REQ), `flows.md`, "
            "`rules.md`, `notes.md` from what the code actually does."
        )
        lines.append(
            f"3. Mark any claim you could not confirm with `{adm.UNVERIFIED_MARKER}`. The "
            "audit tracks those (`FEATURE_DOC_UNVERIFIED`, WARN) so they cannot age into "
            "truth unnoticed."
        )
        lines.append("4. Link the feature from `docs/features/INDEX.md` and the mkdocs nav.")
        lines.append(
            "5. Delete the design doc once nothing true is left in it — that clears "
            "`SPEC_OUTSIDE_FEATURE_DOCS`."
        )
        lines.append("")
        lines.append("| Design doc | Candidate slug | Target files |")
        lines.append("|---|---|---|")
        for entry in migration:
            targets = "<br>".join(f"`{target}`" for target in entry["targets"])
            lines.append(f"| `{entry['spec']}` | `{entry['slug']}` | {targets} |")
        lines.append("")
        lines.append(
            "The slug is a *candidate* derived from the filename; rename it to whatever the "
            "code shows the feature actually is."
        )
        lines.append("")

    lines.append("## File Create/Alter List")
    lines.append("")

    lines.append("### Create")
    if create_files:
        for path in create_files:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("### Deferred Creation (no content/writing task available)")
    if deferred_create:
        for item in deferred_create:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("### Alter")
    if alter_files:
        for path in alter_files:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None")

    absent_ai_files = [
        finding["path"]
        for finding in result["findings"]
        if finding.get("code") == "AI_INSTRUCTION_FILE_ABSENT"
    ]
    lines.append("")
    lines.append("### AI Instruction Files Absent (not created by design)")
    if absent_ai_files:
        for path in absent_ai_files:
            lines.append(f"- `{path}`: present-only check; create manually to receive guidelines.")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Proposed Diffs (not applied)")
    lines.append("")

    if not diffs:
        lines.append("No diffs proposed.")
    else:
        for item in diffs:
            lines.append(f"### {item['type']}: `{item['path']}`")
            lines.append("")
            lines.append("```diff")
            lines.append(item["diff"].rstrip("\n"))
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict docs alignment plan")
    parser.add_argument("repo", nargs="?", default=".", help="Repository path")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--max-diffs", type=int, default=30, help="Max diffs to include")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()

    audit_result = adm.audit_repository(repo)
    create_files, alter_files = collect_actions(audit_result)
    diffs, deferred_create = proposed_diffs(
        repo,
        audit_result,
        create_files,
        alter_files,
        max_diffs=args.max_diffs,
    )

    migration = legacy_spec_migration(repo)
    # Structure only, never a create diff: content that has not been read against the code
    # would be exactly the placeholder-laundering the guardrail exists to prevent.
    for entry in migration:
        for target in entry["targets"]:
            deferred_create.append({"path": target, "reason": MIGRATION_DEFERRED_REASON})

    absent_ai_files = [
        finding["path"]
        for finding in audit_result["findings"]
        if finding["code"] == "AI_INSTRUCTION_FILE_ABSENT"
    ]

    output = {
        "repository": str(repo),
        "mode": audit_result["mode"],
        "summary": audit_result["summary"],
        "findings": sort_findings(audit_result["findings"]),
        "create_files": create_files,
        "deferred_create_files": deferred_create,
        "alter_files": alter_files,
        "diffs": diffs,
        "absent_ai_files": absent_ai_files,
        "legacy_spec_migration": migration,
    }

    if args.format == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(
            build_markdown(
                repo, output, create_files, alter_files, diffs, deferred_create, migration
            )
        )

    blockers = output["summary"]["blocker"]
    return 2 if blockers > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
