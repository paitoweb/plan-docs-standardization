#!/usr/bin/env python3
"""Audit repository documentation against the canonical docs model."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


REQUIRED_FILES = [
    "docs/index.md",
    "docs/PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/GLOSSARY.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/nfr/NON_FUNCTIONAL.md",
    "docs/features/INDEX.md",
    "docs/reports/README.md",
    "docs/requirements-mkdocs.txt",
    "mkdocs.yml",
]

FEATURE_REQUIRED_FILES = ["README.md", "flows.md", "rules.md", "notes.md"]

INDEX_MAP_NAVIGABLE = [
    "docs/PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/GLOSSARY.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/nfr/NON_FUNCTIONAL.md",
    "docs/features/INDEX.md",
    "docs/reports/README.md",
]

AI_INSTRUCTION_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]

AI_INSTRUCTION_SECTION_HEADINGS = [
    "## Workflow: New Feature",
    "## Working Principles",
]

CANONICAL_GUIDELINES_REL = "assets/templates/ai-instructions/guidelines.en.md"

AI_INSTRUCTION_MAP_HEADING = "## Documentation Map"

IGNORED_FILE_NAMES = {".DS_Store"}
IGNORED_PATH_PARTS = {".obsidian", "__pycache__"}

REQ_ID_RE = re.compile(r"\bREQ-[A-Z0-9-]+-\d{3}\b")
AC_ID_RE = re.compile(r"\bAC-[A-Z0-9-]+-\d{3}\b")
NFR_ID_RE = re.compile(r"\bNFR-\d{3}\b")
AC_NFR_ID_RE = re.compile(r"\bAC-NFR-\d{3}\b")

CODE_SPAN_RE = re.compile(r"`([^`]+)`")

AC_HEADING_RE = re.compile(r"^\s*###\s+(AC-[A-Z0-9-]+-\d{3})\b")
AC_NFR_HEADING_RE = re.compile(r"^\s*###\s+(AC-NFR-\d{3})\b")

SECTION_HEADING_RE = re.compile(r"^\s*##\s+(.*\S)\s*$")
TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
ORDERED_ITEM_RE = re.compile(r"^\s*\d+\.\s+\S")
BULLET_ITEM_RE = re.compile(r"^\s*[-*]\s+\S")

SEVERITY_ORDER = {"BLOCKER": 0, "WARN": 1, "INFO": 2}


@dataclass
class Finding:
    severity: str
    code: str
    path: str
    message: str
    line: int | None = None


@dataclass
class AuditSummary:
    blocker: int = 0
    warn: int = 0
    info: int = 0


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_accents.lower()


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def section_span(lines: list[str], heading: str) -> tuple[int, int] | None:
    """Return (start, end) line indices of a level-2 section, end exclusive."""

    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].lstrip().startswith("## "):
            end = index
            break
    return start, end


def extract_section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    span = section_span(lines, heading)
    if span is None:
        return None
    start, end = span
    return "\n".join(lines[start:end])


def load_canonical_sections() -> dict[str, str]:
    template_path = skill_root() / CANONICAL_GUIDELINES_REL
    text = template_path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for heading in AI_INSTRUCTION_SECTION_HEADINGS:
        section = extract_section(text, heading)
        if section is None:
            raise ValueError(f"Canonical template missing section: {heading}")
        sections[heading] = section
    return sections


def load_canonical_map_section() -> str:
    text = (skill_root() / CANONICAL_GUIDELINES_REL).read_text(encoding="utf-8")
    return extract_section(text, AI_INSTRUCTION_MAP_HEADING) or ""


def normalize_section_title(raw_title: str) -> str:
    title = TRAILING_PAREN_RE.sub("", raw_title).strip()
    title = re.sub(r"\s+", " ", title)
    return normalize_text(title)


def feature_section_titles(text: str) -> list[tuple[str, str]]:
    """Return (normalized, original) for each level-2 heading, deduped, in order."""

    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = SECTION_HEADING_RE.match(line)
        if not match:
            continue
        original = match.group(1).strip()
        normalized = normalize_section_title(original)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append((normalized, original))
    return result


def iter_level2_sections(text: str) -> list[list[str]]:
    """Split text into level-2 sections; lines before the first heading are dropped."""

    sections: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if SECTION_HEADING_RE.match(line):
            if current is not None:
                sections.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        sections.append(current)
    return sections


def compute_feature_section_gaps(repo: Path) -> dict[str, list[str]]:
    """Map each feature README (rel path) to the majority sections it is missing.

    A section is "expected" when a strict majority of feature READMEs use it
    (count > readme_count / 2). A section unique to one richer feature never becomes
    expected, so it does not cascade onto the others. Returns {} when there are fewer
    than two feature READMEs.
    """

    feature_sets: list[tuple[str, set[str]]] = []
    counts: dict[str, int] = {}
    first_original: dict[str, str] = {}
    for feature_dir in collect_feature_dirs(repo):
        readme = feature_dir / "README.md"
        if not readme.exists():
            continue
        titles = feature_section_titles(readme.read_text(encoding="utf-8"))
        normalized_set = {normalized for normalized, _ in titles}
        for normalized, original in titles:
            if normalized not in first_original:
                first_original[normalized] = original
        for normalized in normalized_set:
            counts[normalized] = counts.get(normalized, 0) + 1
        feature_sets.append((str(readme.relative_to(repo)), normalized_set))

    readme_count = len(feature_sets)
    if readme_count < 2:
        return {}

    expected = [
        normalized
        for normalized in first_original
        if counts[normalized] > readme_count / 2
    ]

    gaps: dict[str, list[str]] = {}
    for rel, normalized_set in feature_sets:
        missing = [first_original[n] for n in expected if n not in normalized_set]
        if missing:
            gaps[rel] = missing
    return gaps


def check_feature_section_consistency(repo: Path, findings: list[Finding]) -> None:
    for rel, missing in compute_feature_section_gaps(repo).items():
        make_finding(
            findings,
            "WARN",
            "FEATURE_SECTION_INCONSISTENT",
            rel,
            "Feature README missing sections used by the majority of features: "
            + ", ".join(missing),
        )


def should_ignore_path(path: Path) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in path.parts) or path.name in IGNORED_FILE_NAMES


def iter_code_span_tokens(text: str) -> Iterable[str]:
    for token in CODE_SPAN_RE.findall(text):
        candidate = token.strip()
        if candidate:
            yield candidate


def make_finding(
    findings: list[Finding],
    severity: str,
    code: str,
    path: str,
    message: str,
    line: int | None = None,
) -> None:
    findings.append(Finding(severity=severity, code=code, path=path, message=message, line=line))


def discover_mode(repo: Path) -> str:
    docs_dir = repo / "docs"
    return "alignment" if docs_dir.exists() else "bootstrap"


def collect_feature_dirs(repo: Path) -> list[Path]:
    features_dir = repo / "docs" / "features"
    if not features_dir.exists():
        return []

    directories: list[Path] = []
    for child in sorted(features_dir.iterdir()):
        if not child.is_dir():
            continue
        if should_ignore_path(child):
            continue
        if child.name.startswith("."):
            continue
        directories.append(child)
    return directories


def check_required_files(repo: Path, findings: list[Finding]) -> None:
    for rel in REQUIRED_FILES:
        candidate = repo / rel
        if not candidate.exists():
            make_finding(
                findings,
                "BLOCKER",
                "MISSING_REQUIRED_FILE",
                rel,
                f"Required file is missing: {rel}",
            )


def check_feature_files(feature_dir: Path, repo: Path, findings: list[Finding]) -> None:
    rel_feature_dir = feature_dir.relative_to(repo)
    for required_name in FEATURE_REQUIRED_FILES:
        file_path = feature_dir / required_name
        if not file_path.exists():
            make_finding(
                findings,
                "BLOCKER",
                "MISSING_FEATURE_FILE",
                str(rel_feature_dir / required_name),
                f"Feature directory must include {required_name}",
            )


def check_feature_readme(readme_path: Path, repo: Path, findings: list[Finding]) -> None:
    rel = str(readme_path.relative_to(repo))
    content = readme_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for token in sorted(set(iter_code_span_tokens(content))):
        if token.startswith("REQ-"):
            if token.endswith("*"):
                continue
            if not REQ_ID_RE.fullmatch(token):
                make_finding(
                    findings,
                    "BLOCKER",
                    "INVALID_REQ_ID_TOKEN",
                    rel,
                    f"Invalid REQ token format: {token}",
                )

        if token.startswith("AC-") and not token.startswith("AC-NFR-"):
            if token.endswith("*"):
                continue
            if not AC_ID_RE.fullmatch(token):
                make_finding(
                    findings,
                    "BLOCKER",
                    "INVALID_AC_ID_TOKEN",
                    rel,
                    f"Invalid AC token format: {token}",
                )

    req_ids = set(REQ_ID_RE.findall(content))
    ac_ids = set(AC_ID_RE.findall(content))

    if not req_ids:
        make_finding(
            findings,
            "BLOCKER",
            "MISSING_REQ_IDS",
            rel,
            "Feature README does not define any REQ-* IDs",
        )

    if not ac_ids:
        make_finding(
            findings,
            "BLOCKER",
            "MISSING_AC_IDS",
            rel,
            "Feature README does not define any AC-* IDs",
        )

    for line_number, line in enumerate(lines, start=1):
        if not AC_HEADING_RE.search(line):
            continue
        req_refs = REQ_ID_RE.findall(line)
        if not req_refs:
            make_finding(
                findings,
                "BLOCKER",
                "AC_WITHOUT_REQ_REFERENCE",
                rel,
                "AC heading must reference at least one REQ-* ID",
                line=line_number,
            )
            continue

        unknown_refs = sorted(ref for ref in req_refs if ref not in req_ids)
        if unknown_refs:
            make_finding(
                findings,
                "BLOCKER",
                "AC_REF_UNKNOWN_REQ",
                rel,
                f"AC heading references unknown REQ IDs: {', '.join(unknown_refs)}",
                line=line_number,
            )


def check_nfr_file(nfr_path: Path, repo: Path, findings: list[Finding]) -> None:
    if not nfr_path.exists():
        return

    rel = str(nfr_path.relative_to(repo))
    content = nfr_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for token in sorted(set(iter_code_span_tokens(content))):
        if token.startswith("NFR-"):
            if token.endswith("*"):
                continue
            if not NFR_ID_RE.fullmatch(token):
                make_finding(
                    findings,
                    "BLOCKER",
                    "INVALID_NFR_ID_TOKEN",
                    rel,
                    f"Invalid NFR token format: {token}",
                )

        if token.startswith("AC-NFR-"):
            if token.endswith("*"):
                continue
            if not AC_NFR_ID_RE.fullmatch(token):
                make_finding(
                    findings,
                    "BLOCKER",
                    "INVALID_AC_NFR_ID_TOKEN",
                    rel,
                    f"Invalid AC-NFR token format: {token}",
                )

    nfr_ids = set(NFR_ID_RE.findall(content))
    ac_nfr_ids = set(AC_NFR_ID_RE.findall(content))

    if not nfr_ids:
        make_finding(
            findings,
            "BLOCKER",
            "MISSING_NFR_IDS",
            rel,
            "NFR document does not define any NFR-* IDs",
        )

    if not ac_nfr_ids:
        make_finding(
            findings,
            "BLOCKER",
            "MISSING_AC_NFR_IDS",
            rel,
            "NFR document does not define any AC-NFR-* IDs",
        )

    for line_number, line in enumerate(lines, start=1):
        if not AC_NFR_HEADING_RE.search(line):
            continue
        refs = NFR_ID_RE.findall(line)
        if not refs:
            make_finding(
                findings,
                "BLOCKER",
                "AC_NFR_WITHOUT_NFR_REFERENCE",
                rel,
                "AC-NFR heading must reference at least one NFR-* ID",
                line=line_number,
            )
            continue

        unknown_refs = sorted(ref for ref in refs if ref not in nfr_ids)
        if unknown_refs:
            make_finding(
                findings,
                "BLOCKER",
                "AC_NFR_REF_UNKNOWN_NFR",
                rel,
                f"AC-NFR heading references unknown NFR IDs: {', '.join(unknown_refs)}",
                line=line_number,
            )


def strip_code_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """Return (line_number, line) skipping fenced code blocks."""

    output: list[tuple[int, str]] = []
    in_fence = False

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        output.append((index, line))

    return output


def iter_markdown_links(markdown_file: Path) -> Iterable[tuple[int, str]]:
    text = markdown_file.read_text(encoding="utf-8")
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for line_number, line in strip_code_blocks(text.splitlines()):
        for target in link_re.findall(line):
            yield line_number, target.strip()


def is_external_link(target: str) -> bool:
    lower = target.lower()
    return (
        lower.startswith("http://")
        or lower.startswith("https://")
        or lower.startswith("mailto:")
        or lower.startswith("tel:")
    )


def resolve_link_target(repo: Path, source_file: Path, raw_target: str) -> Path | None:
    if not raw_target or is_external_link(raw_target):
        return None

    if raw_target.startswith("#"):
        return None

    target = unquote(raw_target)
    target = target.split("#", maxsplit=1)[0]
    target = target.split("?", maxsplit=1)[0].strip()
    if not target:
        return None

    if target.startswith("/"):
        resolved = repo / target.lstrip("/")
    else:
        resolved = (source_file.parent / target).resolve()

    if resolved.is_dir():
        readme = resolved / "README.md"
        return readme

    return resolved


def check_markdown_links(repo: Path, findings: list[Finding]) -> None:
    docs_dir = repo / "docs"
    if not docs_dir.exists():
        return

    for md_file in sorted(docs_dir.rglob("*.md")):
        if should_ignore_path(md_file):
            continue
        rel = str(md_file.relative_to(repo))

        for line_number, target in iter_markdown_links(md_file):
            resolved = resolve_link_target(repo, md_file, target)
            if resolved is None:
                continue
            if not resolved.exists():
                make_finding(
                    findings,
                    "BLOCKER",
                    "BROKEN_INTERNAL_LINK",
                    rel,
                    f"Broken internal link target: {target}",
                    line=line_number,
                )


def check_index_map(repo: Path, findings: list[Finding]) -> None:
    """WARN when docs/index.md is not a navigational map.

    A map links to a strict majority of the navigable canonical docs. Detection is
    by resolved link target, independent of language. Absent index.md is handled by
    the required-files check, not here.
    """

    index_path = repo / "docs" / "index.md"
    if not index_path.exists():
        return

    navigable = {(repo / rel).resolve() for rel in INDEX_MAP_NAVIGABLE}
    linked: set[Path] = set()
    for _line_number, target in iter_markdown_links(index_path):
        resolved = resolve_link_target(repo, index_path, target)
        if resolved is not None:
            linked.add(resolved.resolve())

    hits = len(navigable & linked)
    if hits * 2 <= len(INDEX_MAP_NAVIGABLE):  # not a strict majority
        make_finding(
            findings,
            "WARN",
            "INDEX_MAP_MISSING",
            "docs/index.md",
            "docs/index.md lacks a documentation map: it links to "
            f"{hits} of {len(INDEX_MAP_NAVIGABLE)} canonical docs. A navigational map "
            "should link to a majority of them.",
        )


def extract_nav_refs(nav_entry: Any) -> list[str]:
    refs: list[str] = []

    if isinstance(nav_entry, str):
        if nav_entry.endswith(".md"):
            refs.append(nav_entry)
        return refs

    if isinstance(nav_entry, list):
        for item in nav_entry:
            refs.extend(extract_nav_refs(item))
        return refs

    if isinstance(nav_entry, dict):
        for value in nav_entry.values():
            refs.extend(extract_nav_refs(value))
        return refs

    return refs


def check_mkdocs_nav(repo: Path, findings: list[Finding]) -> None:
    mkdocs_path = repo / "mkdocs.yml"
    if not mkdocs_path.exists():
        return

    rel = str(mkdocs_path.relative_to(repo))

    if yaml is None:
        make_finding(
            findings,
            "WARN",
            "YAML_MODULE_UNAVAILABLE",
            rel,
            "Cannot validate mkdocs nav because PyYAML is unavailable",
        )
        return

    raw_content = mkdocs_path.read_text(encoding="utf-8")
    sanitized_content = re.sub(r"!ENV\s+", "", raw_content)
    sanitized_content = re.sub(
        r"!!python/name:([A-Za-z0-9_.]+)",
        r'"\1"',
        sanitized_content,
    )

    parse_candidates = [raw_content]
    if sanitized_content != raw_content:
        parse_candidates.append(sanitized_content)

    config = None
    parse_error: Exception | None = None
    for candidate in parse_candidates:
        try:
            config = yaml.safe_load(candidate)
            parse_error = None
            break
        except Exception as exc:  # pragma: no cover
            parse_error = exc

    if parse_error is not None:
        make_finding(
            findings,
            "BLOCKER",
            "MKDOCS_YAML_ERROR",
            rel,
            f"Invalid mkdocs.yml: {parse_error}",
        )
        return

    nav = (config or {}).get("nav")
    if not nav:
        make_finding(
            findings,
            "BLOCKER",
            "MKDOCS_NAV_MISSING",
            rel,
            "mkdocs.yml must define nav",
        )
        return

    for nav_ref in sorted(set(extract_nav_refs(nav))):
        target = repo / "docs" / nav_ref
        if not target.exists():
            make_finding(
                findings,
                "BLOCKER",
                "MKDOCS_NAV_BROKEN",
                rel,
                f"mkdocs nav references missing file: docs/{nav_ref}",
            )


def detect_ai_instruction_shapes(text: str) -> tuple[bool, bool]:
    """Detect (has_workflow, has_principles) by structure, independent of language.

    Workflow = a level-2 section with >=3 ordered-list items.
    Principles = a *different* level-2 section with >=3 bullet items.
    """

    sections = iter_level2_sections(text)
    ordered_indexes = [
        index
        for index, section in enumerate(sections)
        if sum(1 for line in section if ORDERED_ITEM_RE.match(line)) >= 3
    ]
    bullet_indexes = [
        index
        for index, section in enumerate(sections)
        if sum(1 for line in section if BULLET_ITEM_RE.match(line)) >= 3
    ]

    workflow_index = ordered_indexes[0] if ordered_indexes else None
    principles_index = next(
        (index for index in bullet_indexes if index != workflow_index), None
    )
    return workflow_index is not None, principles_index is not None


def references_doc_index(path: Path, repo: Path) -> bool:
    """True when the markdown file links to docs/index.md (by resolved target)."""

    index_resolved = (repo / "docs" / "index.md").resolve()
    for _line_number, target in iter_markdown_links(path):
        resolved = resolve_link_target(repo, path, target)
        if resolved is not None and resolved.resolve() == index_resolved:
            return True
    return False


def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
    for rel in AI_INSTRUCTION_FILES:
        path = repo / rel
        if not path.exists():
            make_finding(
                findings,
                "INFO",
                "AI_INSTRUCTION_FILE_ABSENT",
                rel,
                "AI instruction file absent; skill does not create it. "
                "Create it manually to receive the canonical guidelines.",
            )
            continue

        has_workflow, has_principles = detect_ai_instruction_shapes(
            path.read_text(encoding="utf-8")
        )
        if not has_workflow:
            make_finding(
                findings,
                "BLOCKER",
                "AI_INSTRUCTION_SECTION_MISSING",
                rel,
                "AI instruction file missing a workflow section "
                "(a heading followed by a numbered list of steps).",
            )
        if not has_principles:
            make_finding(
                findings,
                "BLOCKER",
                "AI_INSTRUCTION_SECTION_MISSING",
                rel,
                "AI instruction file missing a principles section "
                "(a heading followed by a bulleted list).",
            )

        if not references_doc_index(path, repo):
            make_finding(
                findings,
                "INFO",
                "AI_INSTRUCTION_MAP_POINTER_MISSING",
                rel,
                "AI instruction file does not reference docs/index.md (the documentation "
                "map). Add a pointer so agents consult the map before writing docs.",
            )


def summarize(findings: list[Finding]) -> AuditSummary:
    summary = AuditSummary()
    for finding in findings:
        if finding.severity == "BLOCKER":
            summary.blocker += 1
        elif finding.severity == "WARN":
            summary.warn += 1
        else:
            summary.info += 1
    return summary


def sort_findings(findings: list[Finding]) -> list[Finding]:
    def key(item: Finding) -> tuple[int, str, int, str]:
        return (
            SEVERITY_ORDER.get(item.severity, 9),
            item.path,
            item.line or 0,
            item.code,
        )

    return sorted(findings, key=key)


def audit_repository(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    findings: list[Finding] = []

    mode = discover_mode(repo)

    check_required_files(repo, findings)

    feature_dirs = collect_feature_dirs(repo)
    for feature_dir in feature_dirs:
        check_feature_files(feature_dir, repo, findings)
        readme = feature_dir / "README.md"
        if readme.exists():
            check_feature_readme(readme, repo, findings)

    check_feature_section_consistency(repo, findings)

    nfr_file = repo / "docs" / "nfr" / "NON_FUNCTIONAL.md"
    check_nfr_file(nfr_file, repo, findings)
    check_markdown_links(repo, findings)
    check_mkdocs_nav(repo, findings)
    check_index_map(repo, findings)
    check_ai_instruction_files(repo, findings)

    sorted_findings = sort_findings(findings)
    summary = summarize(sorted_findings)

    return {
        "repository": str(repo),
        "mode": mode,
        "feature_directories": [str(p.relative_to(repo)) for p in feature_dirs],
        "summary": asdict(summary),
        "findings": [asdict(item) for item in sorted_findings],
    }


def to_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    findings = result["findings"]

    lines: list[str] = []
    lines.append("# Documentation Model Audit")
    lines.append("")
    lines.append(f"- Repository: `{result['repository']}`")
    lines.append(f"- Mode: `{result['mode']}`")
    lines.append(
        f"- Summary: {summary['blocker']} BLOCKER, {summary['warn']} WARN, {summary['info']} INFO"
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

    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit docs model compliance")
    parser.add_argument("repo", nargs="?", default=".", help="Repository path")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo)

    result = audit_repository(repo)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(result))

    blockers = result["summary"]["blocker"]
    return 2 if blockers > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
