#!/usr/bin/env python3
"""Audit implementation traceability: REQ citations in source, AC/REQ in tests."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_docs_model as adm  # noqa: E402

REQ_ID_RE = re.compile(r"\bREQ-[A-Z0-9-]+-\d{3}\b")
AC_ID_RE = re.compile(r"\bAC-[A-Z0-9-]+-\d{3}\b")
TRACEABILITY_COMMENT_RE = re.compile(r"Traceability\s*:", re.IGNORECASE)
SOURCE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".dart", ".py", ".go", ".rs", ".swift", ".kt"}

IGNORED_PATH_PARTS = {".git", "node_modules", ".old", "dist", "build", ".dart_tool"}


@dataclass
class FeatureTraceabilityConfig:
    feature_dir: str
    source_globs: list[str]
    test_globs: list[str]
    exclude_globs: list[str]


def load_traceability_config(repo: Path) -> list[FeatureTraceabilityConfig] | None:
    config_path = repo / "docs" / "traceability.json"
    if not config_path.exists():
        return None

    data = json.loads(config_path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    configs: list[FeatureTraceabilityConfig] = []
    for item in features:
        if not item.get("feature_dir"):
            continue
        configs.append(
            FeatureTraceabilityConfig(
                feature_dir=item["feature_dir"],
                source_globs=list(item.get("source_globs", [])),
                test_globs=list(item.get("test_globs", [])),
                exclude_globs=list(item.get("exclude_globs", [])),
            )
        )
    return configs


def feature_req_ids(repo: Path, feature_dir: str) -> set[str]:
    readme = repo / "docs" / "features" / feature_dir / "README.md"
    if not readme.exists():
        return set()
    return set(REQ_ID_RE.findall(readme.read_text(encoding="utf-8")))


def should_ignore_path(path: Path) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in path.parts)


def expand_globs(repo: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        if "**" in pattern:
            base = pattern.split("**", 1)[0].rstrip("/")
            search_root = repo / base if base else repo
            if not search_root.exists():
                continue
            suffix = pattern.split("**", 1)[1].lstrip("/")
            for candidate in search_root.rglob(suffix or "*"):
                if candidate.is_file() and not should_ignore_path(candidate.relative_to(repo)):
                    files.append(candidate)
        else:
            for candidate in repo.glob(pattern):
                if candidate.is_file() and not should_ignore_path(candidate.relative_to(repo)):
                    files.append(candidate)
    return sorted(set(files))


def matches_any_glob(rel_posix: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_posix, pattern) for pattern in patterns)


def file_req_ids(text: str) -> set[str]:
    return set(REQ_ID_RE.findall(text))


def file_has_traceability_comment(text: str) -> bool:
    if not TRACEABILITY_COMMENT_RE.search(text):
        return False
    return bool(REQ_ID_RE.search(text) or AC_ID_RE.search(text))


def audit_code_traceability(repo: Path) -> list[adm.Finding]:
    repo = repo.resolve()
    findings: list[adm.Finding] = []
    configs = load_traceability_config(repo)

    if configs is None:
        if (repo / ".cursor").is_dir() and adm.discover_mode(repo) == "alignment":
            adm.make_finding(
                findings,
                "BLOCKER",
                "TRACEABILITY_CONFIG_MISSING",
                "docs/traceability.json",
                "Cursor Docs-First projects MUST define docs/traceability.json "
                "mapping features to source and test globs.",
            )
        return findings

    for config in configs:
        req_ids = feature_req_ids(repo, config.feature_dir)
        if not req_ids:
            adm.make_finding(
                findings,
                "WARN",
                "TRACEABILITY_FEATURE_NO_REQS",
                f"docs/features/{config.feature_dir}/README.md",
                f"Feature '{config.feature_dir}' has no REQ-* IDs in README.",
            )
            continue

        source_files = [
            path
            for path in expand_globs(repo, config.source_globs)
            if not matches_any_glob(path.relative_to(repo).as_posix(), config.exclude_globs)
            and path.suffix in SOURCE_EXTENSIONS
        ]
        test_files = [
            path
            for path in expand_globs(repo, config.test_globs)
            if path.suffix in SOURCE_EXTENSIONS
        ]

        if not source_files:
            adm.make_finding(
                findings,
                "WARN",
                "TRACEABILITY_NO_SOURCE_FILES",
                f"docs/traceability.json ({config.feature_dir})",
                "No source files matched source_globs.",
            )

        for path in source_files:
            rel = path.relative_to(repo).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            cited = file_req_ids(text)
            if not cited:
                adm.make_finding(
                    findings,
                    "BLOCKER",
                    "SOURCE_MISSING_REQ_CITATION",
                    rel,
                    "Source file implements feature logic but cites no REQ-* ID. "
                    "Add a file header or construct doc comment referencing the REQ.",
                )
                continue
            unmatched = cited - req_ids
            if unmatched and not cited & req_ids:
                adm.make_finding(
                    findings,
                    "BLOCKER",
                    "SOURCE_REQ_NOT_IN_FEATURE",
                    rel,
                    f"Cited REQ IDs {sorted(unmatched)} are not declared in "
                    f"docs/features/{config.feature_dir}/README.md.",
                )

        if not test_files:
            adm.make_finding(
                findings,
                "BLOCKER",
                "TEST_FILES_MISSING",
                f"docs/traceability.json ({config.feature_dir})",
                "No test files matched test_globs; every feature MUST have tests "
                "with Traceability comments.",
            )
            continue

        for path in test_files:
            rel = path.relative_to(repo).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not file_has_traceability_comment(text):
                adm.make_finding(
                    findings,
                    "BLOCKER",
                    "TEST_MISSING_TRACEABILITY",
                    rel,
                    "Test file must include a 'Traceability:' comment referencing "
                    "at least one AC-* or REQ-* ID from the feature docs.",
                )

    return findings


def audit_repository(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    findings = audit_code_traceability(repo)
    sorted_findings = adm.sort_findings(findings)
    summary = adm.summarize(sorted_findings)
    return {
        "repository": str(repo),
        "audit": "code_traceability",
        "summary": asdict(summary),
        "findings": [asdict(item) for item in sorted_findings],
    }


def to_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    findings = result["findings"]
    lines = [
        "# Code Traceability Audit",
        "",
        f"- Repository: `{result['repository']}`",
        f"- Summary: {summary['blocker']} BLOCKER, {summary['warn']} WARN, {summary['info']} INFO",
        "",
        "## Compliance Matrix (BLOCKER/WARN/INFO)",
        "",
        "| Severity | Code | File | Message |",
        "|---|---|---|---|",
    ]
    if not findings:
        lines.append("| INFO | CLEAN | - | All source and test traceability checks passed |")
    else:
        for finding in findings:
            message = finding["message"].replace("|", "\\|")
            lines.append(
                f"| {finding['severity']} | {finding['code']} | `{finding['path']}` | {message} |"
            )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Audit code/test traceability")
    parser.add_argument("repo", nargs="?", default=".", help="Repository path")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args(argv)

    result = audit_repository(Path(args.repo))
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(result))
    return 2 if result["summary"]["blocker"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
