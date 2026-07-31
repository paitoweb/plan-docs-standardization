#!/usr/bin/env python3
"""Audit repository documentation against the canonical docs model."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
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

import agent_profiles as _ap
import docs_first_config as _dfc
import enforcement_gates as _eg

KNOWN_ENFORCEMENT_GATES = {"ci", "local-hook", "claude-hooks", "codex-hooks"}


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

# The canonical block is a single source of truth that gets *copied* into each consumer
# repository, so copies drift the moment the source changes. Nothing else detects that: the
# shape check (R010) and the path reference (R011) both keep passing on a block that is two
# revisions old. Bump this whenever guidelines.en.md changes in a way consumers need.
#
# The marker lives *inside* the workflow section, not above it: the skill installs the block
# by appending those sections, so a marker in the preamble would never reach a consumer.
CANONICAL_BLOCK_VERSION = 2

BLOCK_VERSION_RE = re.compile(r"<!--\s*docs-first-block:\s*(\d+)\s*-->")

# The path the workflow must route feature work through. A literal path, so requiring it
# keeps the content check language-agnostic.
FEATURE_DOCS_REF = "docs/features/"

DEFAULT_DIFF_BASE = "origin/main"

# Marks a claim in a feature doc that has not yet been read against the implementation.
# Same `docs-first:` token family as the --diff escape hatch; deliberately not bracketed,
# since a [bracketed] token reads as a markdown link and as a template placeholder.
UNVERIFIED_MARKER = "docs-first:unverified"

# Opt-out marker, honored anywhere in the range's commit messages: some changes legitimately
# touch code without touching a feature doc (refactors, chores, build config).
DIFF_SKIP_MARKER = "docs-first: skip"

# What counts as "code" in --diff mode. An extension allowlist, not "everything that is not
# a doc": the latter flags a lockfile bump or a CI tweak as feature work, and a rule that
# cries wolf on every chore is a rule people turn off. Extend per repo with
# `code_extensions` in .docs-first/config.yml.
# Test paths are exempt by default. A test-only change ships no behavior, so flagging it
# would be a false positive; and nothing is lost, because a feature that ships code *and*
# tests is still caught by its code files. Config globs extend this set, never replace it.
DEFAULT_DIFF_EXEMPT_GLOBS = (
    "tests/*",
    "test/*",
    "spec/*",
    "*/tests/*",
    "*/test/*",
    "*/__tests__/*",
    "*.test.*",
    "*.spec.*",
    "*_test.*",
    "*_spec.*",
)

# Where code lives, when the repo has not declared `code_roots`. Directory names, so this
# stays stack-neutral instead of sniffing manifests per ecosystem.
CONVENTIONAL_CODE_ROOTS = ("src", "lib", "app", "apps", "packages", "internal", "pkg", "cmd")

# Directory names that are never a feature: build output, dependencies, tests, and buckets
# that hold no domain behavior. Kept deliberately short -- names like components/ or hooks/
# stay candidates, because in many apps they really do contain features.
NON_FEATURE_CODE_DIRS = frozenset(
    {
        "__mocks__", "__tests__", "assets", "build", "coverage", "dist", "fixtures",
        "migrations", "node_modules", "out", "spec", "styles", "target", "test", "tests",
        "typings", "types", "vendor",
    }
)

# Below this share of candidate code units having a matching feature doc, the aggregate
# coverage finding fires. A heuristic default, not a calibrated number -- it exists so the
# rule says something in a repo that configured nothing, which is the case it was built for.
DEFAULT_COVERAGE_MIN = 50

DEFAULT_CODE_EXTENSIONS = frozenset(
    {
        ".c", ".cc", ".cpp", ".cs", ".dart", ".ex", ".exs", ".go", ".h", ".hpp", ".java",
        ".js", ".jsx", ".kt", ".kts", ".m", ".mm", ".php", ".py", ".rb", ".rs", ".scala",
        ".sql", ".svelte", ".swift", ".ts", ".tsx", ".vue",
    }
)

IGNORED_FILE_NAMES = {".DS_Store"}
IGNORED_PATH_PARTS = {".obsidian", "__pycache__"}

# Design-doc artifacts produced by tooling sit outside the model: docs/features/ is the
# single source of truth for feature behavior. A dated design doc is abandoned by
# definition, so the subtree is excluded entirely — its stale links must not fail the gate.
IGNORED_DOCS_SUBTREES = ("docs/superpowers/specs",)

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


def is_ignored_docs_subtree(path: Path, repo: Path) -> bool:
    """True when path lives in a docs subtree the model excludes (design-doc artifacts)."""

    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return False
    return any(
        rel == prefix or rel.startswith(prefix + "/") for prefix in IGNORED_DOCS_SUBTREES
    )


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


def normalize_slug(value: str) -> str:
    """Fold a directory name and a feature slug onto a comparable form.

    `voiceTranscription`, `voice-transcription` and `voice_transcription` are the same
    feature wearing three naming conventions.
    """

    return re.sub(r"[^a-z0-9]", "", normalize_text(value))


def resolve_code_roots(repo: Path, declared: list[str]) -> list[Path]:
    names = declared or CONVENTIONAL_CODE_ROOTS
    return [repo / name for name in names if (repo / name).is_dir()]


def candidate_code_units(repo: Path, roots: list[Path]) -> list[Path]:
    """Immediate subdirectories of each code root that could plausibly be a feature."""

    units: list[Path] = []
    for root in roots:
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name.lower() in NON_FEATURE_CODE_DIRS or should_ignore_path(child):
                continue
            units.append(child)
    return units


def check_code_to_docs_coverage(repo: Path, findings: list[Finding]) -> None:
    """Detect features that exist in code but not in docs/features/.

    Two instruments with very different precision, deliberately kept apart:

    - The declared `feature_map` is exact. A mapped code path that exists with no matching
      feature doc is a BLOCKER, because the repo itself asserted that mapping.
    - The coverage ratio is a *smell signal*, not a measurement. It compares counts of
      things that are not strictly comparable (a layered architecture has directories per
      layer, not per feature), so it is one aggregate WARN and never per-directory: in a
      repo like the reported one, per-directory findings would mark nearly every folder and
      train the reader to ignore the audit.

    Alignment mode only. In bootstrap there are no docs yet, so "coverage is low" is noise.
    """

    if discover_mode(repo) != "alignment":
        return

    config = _dfc.load_config(repo)
    documented = {normalize_slug(path.name) for path in collect_feature_dirs(repo)}

    mapped_pairs: list[tuple[str, str]] = []
    if config:
        mapped_pairs, _malformed = _dfc.parse_feature_map(config.feature_map)

    for code_path, slug in mapped_pairs:
        target = repo / code_path
        if not target.exists():
            continue
        if normalize_slug(slug) not in documented:
            make_finding(
                findings,
                "BLOCKER",
                "FEATURE_DOC_MISSING",
                code_path,
                f"{code_path} is mapped to feature {slug!r} in .docs-first/config.yml, but "
                f"docs/features/{slug}/ does not exist. The code ships behavior that no "
                "feature doc describes.",
            )

    roots = resolve_code_roots(repo, config.code_roots if config else [])
    if not roots:
        return

    mapped_units = {(repo / code_path).resolve() for code_path, _slug in mapped_pairs}
    # Skip what the map already covers: the heuristic exists to survey unmapped territory,
    # not to second-guess the precise instrument.
    candidates = [
        unit
        for unit in candidate_code_units(repo, roots)
        if unit.resolve() not in mapped_units
    ]
    if not candidates:
        return

    covered = [unit for unit in candidates if normalize_slug(unit.name) in documented]
    coverage = len(covered) * 100 // len(candidates)

    minimum = DEFAULT_COVERAGE_MIN
    if config and config.coverage_min is not None:
        minimum = config.coverage_min
    if coverage >= minimum:
        return

    orphans = [unit.relative_to(repo).as_posix() for unit in candidates if unit not in covered]
    listed = ", ".join(orphans[:5])
    if len(orphans) > 5:
        listed += f", +{len(orphans) - 5} more"

    severity = "BLOCKER" if config and config.coverage_gate else "WARN"
    make_finding(
        findings,
        severity,
        "FEATURE_DOC_COVERAGE_LOW",
        "docs/features",
        f"{len(covered)} of {len(candidates)} candidate code units have a matching feature "
        f"doc ({coverage}%, below {minimum}%). This is a smell signal, not a measurement: "
        "candidates are directories, which in a layered architecture do not map 1:1 to "
        "features. For an exact check, declare feature_map in .docs-first/config.yml. "
        f"Unmatched: {listed}.",
    )


def git_output(repo: Path, args: list[str]) -> str | None:
    """Run a read-only git command; None when git fails or is unavailable.

    Read-only by construction, so this does not breach the planning-only guardrail.
    """

    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):  # pragma: no cover - git absent from PATH
        return None

    if result.returncode != 0:
        return None
    return result.stdout


def is_code_path(path: str, extensions: set[str], exempt_globs: list[str]) -> bool:
    if any(fnmatch.fnmatch(path, pattern) for pattern in exempt_globs):
        return False
    return Path(path).suffix.lower() in extensions


def check_diff_feature_docs(repo: Path, findings: list[Finding], base: str) -> None:
    """BLOCKER when a diff touches code but no feature doc. Only runs with --diff.

    Cheap PR-time enforcement: the audit is otherwise blind to code, so a feature can ship
    fully implemented and fully undocumented while every rule passes. This does not attempt
    to decide *which* feature doc was owed -- only that shipping code while touching no
    feature doc at all is a gap worth stopping.

    An unresolvable base or an unavailable git is a WARN, never a BLOCKER: failing someone's
    pipeline because a ref is missing punishes the wrong mistake.
    """

    config = _dfc.load_config(repo)
    exempt_globs = list(DEFAULT_DIFF_EXEMPT_GLOBS)
    if config:
        exempt_globs.extend(config.diff_exempt_globs)
    extensions = {ext.lower() for ext in (config.code_extensions if config else [])}
    if not extensions:
        extensions = set(DEFAULT_CODE_EXTENSIONS)

    if git_output(repo, ["rev-parse", "--verify", base]) is None:
        make_finding(
            findings,
            "WARN",
            "DIFF_BASE_UNRESOLVED",
            base,
            f"Cannot resolve diff base {base!r} (or git is unavailable), so the "
            "code-without-feature-doc check was skipped. Pass an existing ref via "
            "--diff <ref>.",
        )
        return

    # Three-dot: changes on this branch since it diverged from base, which is what a PR
    # actually contributes -- not everything that landed on base meanwhile.
    names = git_output(repo, ["diff", "--name-only", f"{base}...HEAD"])
    if names is None:
        make_finding(
            findings,
            "WARN",
            "DIFF_BASE_UNRESOLVED",
            base,
            f"git diff against {base!r} failed, so the code-without-feature-doc check "
            "was skipped.",
        )
        return

    changed = [line.strip() for line in names.splitlines() if line.strip()]
    if not changed:
        return

    # Honored anywhere in the range, not just HEAD: in CI HEAD is often a merge commit whose
    # message nobody wrote.
    commit_messages = git_output(repo, ["log", "--pretty=%B", f"{base}...HEAD"]) or ""
    if DIFF_SKIP_MARKER in commit_messages:
        return

    if any(path.startswith(FEATURE_DOCS_REF) for path in changed):
        return

    code_paths = sorted(
        path for path in changed if is_code_path(path, extensions, exempt_globs)
    )
    if not code_paths:
        return

    listed = ", ".join(code_paths[:5])
    if len(code_paths) > 5:
        listed += f", +{len(code_paths) - 5} more"

    make_finding(
        findings,
        "BLOCKER",
        "DIFF_CODE_WITHOUT_FEATURE_DOC",
        FEATURE_DOCS_REF,
        f"{len(code_paths)} code file(s) changed against {base} with no change under "
        f"docs/features/: {listed}. Document the behavior in the feature doc, or mark the "
        f"change exempt with '{DIFF_SKIP_MARKER}' in a commit message (refactors, chores, "
        "build config) or via diff_exempt_globs in .docs-first/config.yml.",
    )


def check_feature_indexing(repo: Path, findings: list[Finding]) -> None:
    """BLOCKER when a feature folder is unreachable from the index or the nav.

    R008 validates nav -> file and R013 validates index -> canonical docs; nothing validated
    feature -> index, so a documented feature that nobody can navigate to passed. A feature
    the reader cannot find is, in practice, undocumented.
    """

    feature_dirs = collect_feature_dirs(repo)
    if not feature_dirs:
        return

    index_path = repo / "docs" / "features" / "INDEX.md"
    indexed: set[Path] = set()
    if index_path.exists():
        for _line_number, target in iter_markdown_links(index_path):
            resolved = resolve_link_target(repo, index_path, target)
            if resolved is not None:
                indexed.add(resolved.resolve())

    nav_refs = mkdocs_nav_refs(repo)
    nav_targets = {(repo / "docs" / ref).resolve() for ref in nav_refs}
    # Only enforce nav coverage when the nav actually enumerates features. Setups built on
    # mkdocs-awesome-pages or literate-nav never list files, and flagging every feature in a
    # legitimate configuration like that would be a pure false positive.
    nav_enumerates_features = any(ref.startswith("features/") for ref in nav_refs)

    for feature_dir in feature_dirs:
        rel = str(feature_dir.relative_to(repo))
        # A link to the folder resolves to its README.md (see resolve_link_target), so
        # matching against the feature's markdown files covers both link styles.
        documents = {path.resolve() for path in feature_dir.rglob("*.md")}

        if not documents & indexed:
            make_finding(
                findings,
                "BLOCKER",
                "FEATURE_NOT_IN_INDEX",
                rel,
                f"Feature {feature_dir.name!r} is not linked from docs/features/INDEX.md. "
                "Add it to the feature catalog: a feature the reader cannot find is "
                "undocumented in practice.",
            )

        if nav_enumerates_features and not documents & nav_targets:
            make_finding(
                findings,
                "BLOCKER",
                "FEATURE_NOT_IN_NAV",
                rel,
                f"Feature {feature_dir.name!r} is absent from the mkdocs nav, which "
                "enumerates other features. Add it so the published site includes it.",
            )


def spec_to_candidate_slug(spec_filename: str) -> str:
    """Candidate feature slug for a legacy design-doc filename.

    `2026-06-09-voice-transcription-design.md` -> `voice-transcription`. A *candidate*: the
    filename suggests what the feature might be called, nothing more.
    """

    stem = re.sub(r"\.md$", "", spec_filename)
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    stem = re.sub(r"-design$", "", stem)
    return stem


def check_unverified_claims(repo: Path, findings: list[Finding]) -> None:
    """WARN per feature whose doc still carries claims not read against the code.

    Migrating a legacy design doc must not launder stale content into the source of truth:
    a dated spec drifts from the implementation, so every claim copied out of one is a
    hypothesis until confirmed. The marker records that state; this rule keeps it tracked,
    so it cannot age quietly into truth -- which is precisely how the design doc came to
    lie in the first place.

    WARN, never BLOCKER: blocking would force whole-feature verification before anything
    can land, making incremental migration impossible.
    """

    for feature_dir in collect_feature_dirs(repo):
        occurrences = 0
        for path in sorted(feature_dir.rglob("*.md")):
            if should_ignore_path(path):
                continue
            occurrences += path.read_text(encoding="utf-8").count(UNVERIFIED_MARKER)

        if not occurrences:
            continue

        make_finding(
            findings,
            "WARN",
            "FEATURE_DOC_UNVERIFIED",
            str(feature_dir.relative_to(repo)),
            f"{occurrences} claim(s) marked '{UNVERIFIED_MARKER}' in this feature doc have "
            "not been read against the implementation. Confirm each against the code and "
            "remove the marker; until then this doc is a hypothesis, not the source of "
            "truth.",
        )


def check_specs_outside_feature_docs(repo: Path, findings: list[Finding]) -> None:
    """WARN once per excluded design-doc subtree that still holds documents.

    docs/features/ is the single source of truth, so a design doc here is either
    pre-adoption legacy or an agent that ignored the redirect in the canonical block.
    Reported as one aggregate finding per subtree: a legacy repo can hold dozens, and the
    resolution is identical for all of them (migrate what is still true, delete the rest),
    so one finding per file would only drown the rest of the audit.
    """

    for prefix in IGNORED_DOCS_SUBTREES:
        subtree = repo / prefix
        if not subtree.is_dir():
            continue

        documents = sorted(
            path for path in subtree.rglob("*.md") if not should_ignore_path(path)
        )
        if not documents:
            continue

        names = [path.relative_to(subtree).as_posix() for path in documents[:5]]
        listed = ", ".join(names)
        if len(documents) > len(names):
            listed += f", +{len(documents) - len(names)} more"

        make_finding(
            findings,
            "WARN",
            "SPEC_OUTSIDE_FEATURE_DOCS",
            prefix,
            f"{len(documents)} design document(s) under {prefix}/. The spec belongs in "
            "docs/features/<feature>/ (the single source of truth for feature behavior). "
            "Migrate what is still true into the feature docs and remove the rest: "
            f"{listed}.",
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
        if should_ignore_path(md_file) or is_ignored_docs_subtree(md_file, repo):
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


def load_mkdocs_config(mkdocs_path: Path) -> tuple[Any | None, Exception | None]:
    """Parse mkdocs.yml, tolerating mkdocs-specific YAML tags (!ENV, !!python/name:)."""

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

    parse_error: Exception | None = None
    for candidate in parse_candidates:
        try:
            return yaml.safe_load(candidate), None
        except Exception as exc:  # pragma: no cover
            parse_error = exc

    return None, parse_error


def mkdocs_nav_refs(repo: Path) -> set[str]:
    """Markdown paths (relative to `docs/`) enumerated in the nav; empty when unavailable.

    Stays silent on absent PyYAML, missing mkdocs.yml and parse errors: check_mkdocs_nav
    already reports each of those, and a second finding for the same cause is only noise.
    """

    mkdocs_path = repo / "mkdocs.yml"
    if yaml is None or not mkdocs_path.exists():
        return set()

    config, parse_error = load_mkdocs_config(mkdocs_path)
    if parse_error is not None:
        return set()

    return set(extract_nav_refs((config or {}).get("nav") or []))


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

    config, parse_error = load_mkdocs_config(mkdocs_path)

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


def _shape_indexes(sections: list[list[str]]) -> tuple[int | None, int | None]:
    """(workflow_index, principles_index) over level-2 sections.

    Single definition of "which section is the workflow", shared by the shape check and the
    content check below — if the two disagreed, we would demand a `docs/features/` reference
    from a section that is not the workflow.
    """

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
    return workflow_index, principles_index


def detect_ai_instruction_shapes(text: str) -> tuple[bool, bool]:
    """Detect (has_workflow, has_principles) by structure, independent of language.

    Workflow = a level-2 section with >=3 ordered-list items.
    Principles = a *different* level-2 section with >=3 bullet items.
    """

    workflow_index, principles_index = _shape_indexes(iter_level2_sections(text))
    return workflow_index is not None, principles_index is not None


def workflow_section_text(text: str) -> str | None:
    """The detected workflow section, or None when the file has no such shape."""

    sections = iter_level2_sections(text)
    workflow_index, _principles_index = _shape_indexes(sections)
    if workflow_index is None:
        return None
    return "\n".join(sections[workflow_index])


def workflow_routes_through_feature_docs(text: str) -> bool:
    """True when the workflow section references docs/features/.

    Content check that stays language-agnostic: `docs/features/` is a literal path, not
    natural language, so this works on localized guidelines — the same trick R014 uses with
    resolved link targets. Structure alone is not enough: any numbered list of three steps
    satisfies the shape check, so a release ritual can pass with no mention of documenting
    anything.
    """

    section = workflow_section_text(text)
    return section is not None and FEATURE_DOCS_REF in section


def installed_block_version(text: str) -> int | None:
    """Version of the canonical block copied into this file, or None when unmarked."""

    match = BLOCK_VERSION_RE.search(text)
    return int(match.group(1)) if match else None


def check_block_version(rel: str, text: str, findings: list[Finding]) -> None:
    """Reconcile a repo's copy of the canonical block against the skill's current one.

    The block is copied, never linked, so a repo that installed it correctly months ago is
    silently running an old one: every structural rule still passes. This is the same
    pathology as the dated design doc, one level up -- a copied artifact nobody reconciles
    with its source.
    """

    installed = installed_block_version(text)

    if installed is None:
        make_finding(
            findings,
            "INFO",
            "AI_INSTRUCTION_BLOCK_UNVERSIONED",
            rel,
            "No canonical-block version marker, so improvements to the block never reach "
            "this file: the guidelines were hand-written or copied before versioning "
            "existed. Install the current block with "
            "`render_profile_artifacts.py <profile>`. If your guidelines are a "
            f"translation, keep them and add `<!-- docs-first-block: "
            f"{CANONICAL_BLOCK_VERSION} -->` for the version you translated — the marker "
            "is language-neutral.",
        )
        return

    if installed < CANONICAL_BLOCK_VERSION:
        make_finding(
            findings,
            "WARN",
            "AI_INSTRUCTION_BLOCK_STALE",
            rel,
            f"Canonical block is version {installed}; the skill ships version "
            f"{CANONICAL_BLOCK_VERSION}. The structural rules still pass, which is exactly "
            "why this needs saying: the file looks compliant while missing everything the "
            "block gained since. Regenerate with "
            "`render_profile_artifacts.py <profile>` and replace the block's sections.",
        )
        return

    if installed > CANONICAL_BLOCK_VERSION:
        make_finding(
            findings,
            "INFO",
            "AI_INSTRUCTION_BLOCK_AHEAD",
            rel,
            f"Canonical block is version {installed}, newer than the skill's "
            f"{CANONICAL_BLOCK_VERSION}. The installed skill is behind, not the repo — "
            "update the skill rather than editing this file.",
        )


def references_doc_index(path: Path, repo: Path) -> bool:
    """True when the markdown file links to docs/index.md (by resolved target)."""

    index_resolved = (repo / "docs" / "index.md").resolve()
    for _line_number, target in iter_markdown_links(path):
        resolved = resolve_link_target(repo, path, target)
        if resolved is not None and resolved.resolve() == index_resolved:
            return True
    return False


def ai_instruction_targets(repo: Path) -> list[str]:
    """Flat AI-instruction files plus each active profile's soft target (deduped)."""

    targets = list(AI_INSTRUCTION_FILES)
    active, _source = _ap.resolve_active_profiles(repo)
    for key in active:
        soft_target = _ap.PROFILES[key].soft_target
        if soft_target not in targets:
            targets.append(soft_target)
    return targets


def check_ai_instruction_files(repo: Path, findings: list[Finding]) -> None:
    for rel in ai_instruction_targets(repo):
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

        text = path.read_text(encoding="utf-8")
        has_workflow, has_principles = detect_ai_instruction_shapes(text)
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

        # Only when the shape exists: a missing workflow section is already reported above,
        # and demanding a reference from a section that is absent would double-report it.
        if has_workflow and not workflow_routes_through_feature_docs(text):
            make_finding(
                findings,
                "BLOCKER",
                "AI_INSTRUCTION_FEATURE_DOC_UNREFERENCED",
                rel,
                "Workflow section does not reference docs/features/. The workflow must "
                "route feature work through the feature doc (docs/features/<feature>/), "
                "which is the spec. Without this, any numbered list of three steps "
                "satisfies the structural check while saying nothing about documenting "
                "features.",
            )

        # Only once the block is structurally there. When a section is missing we are
        # already telling them to install the block; its version is not the news.
        if has_workflow and has_principles:
            check_block_version(rel, text, findings)

        if not references_doc_index(path, repo):
            make_finding(
                findings,
                "INFO",
                "AI_INSTRUCTION_MAP_POINTER_MISSING",
                rel,
                "AI instruction file does not reference docs/index.md (the documentation "
                "map). Add a pointer so agents consult the map before writing docs.",
            )


def check_agent_profiles_config(repo: Path, findings: list[Finding]) -> None:
    """Validate .docs-first/config.yml when present. Absent file is not a finding
    (detection/asking is skill behavior, not the audit's job)."""

    config = _dfc.load_config(repo)
    if config is None:
        return

    unknown_profiles = [p for p in config.profiles if p not in _ap.PROFILES]
    unknown_gates = [
        g
        for g in (config.enforcement_chosen + config.enforcement_declined)
        if g not in KNOWN_ENFORCEMENT_GATES
    ]
    _pairs, malformed_map = _dfc.parse_feature_map(config.feature_map)
    bad_coverage_min = (
        config.coverage_min is not None and not 0 <= config.coverage_min <= 100
    )

    if unknown_profiles or unknown_gates or malformed_map or bad_coverage_min:
        details = []
        if unknown_profiles:
            details.append(f"unknown profiles {sorted(set(unknown_profiles))}")
        if unknown_gates:
            details.append(f"unknown enforcement gates {sorted(set(unknown_gates))}")
        if malformed_map:
            details.append(
                f"malformed feature_map entries {sorted(set(malformed_map))} "
                "(expected 'code/path=feature-slug')"
            )
        if bad_coverage_min:
            details.append(f"coverage_min {config.coverage_min} outside 0-100")
        make_finding(
            findings,
            "WARN",
            "DOCS_FIRST_CONFIG_INVALID",
            _dfc.CONFIG_REL,
            f".docs-first/config.yml has {'; '.join(details)}.",
        )


def check_enforcement_gates(repo: Path, findings: list[Finding]) -> None:
    """Reconcile chosen enforcement gates (.docs-first/config.yml) with what is on disk.

    Chosen-but-missing -> WARN. Nothing chosen and nothing present (docs repo only)
    -> INFO. Never a BLOCKER — the skill never forces a gate.
    """

    config = _dfc.load_config(repo)
    chosen = set(config.enforcement_chosen) if config else set()
    present = {g for g in KNOWN_ENFORCEMENT_GATES if _eg.gate_present(repo, g)}

    for gate in sorted(chosen - present):
        make_finding(
            findings,
            "WARN",
            "ENFORCEMENT_GATE_MISSING",
            _eg.GATE_PATHS.get(gate, gate),
            f"Enforcement gate '{gate}' is chosen in .docs-first/config.yml but not "
            "installed. Re-install it or remove it from the config.",
        )

    if not chosen and not present and discover_mode(repo) == "alignment":
        make_finding(
            findings,
            "INFO",
            "NO_ENFORCEMENT_GATE",
            ".docs-first/config.yml",
            "No enforcement gate active. The Docs-First model is advisory only; "
            "code can drift from docs. Consider a CI/branch-protection or pre-commit gate.",
        )


def check_current_state_suggestion(repo: Path, findings: list[Finding]) -> None:
    """Recommend the optional operational snapshot when absent (docs repo only).

    INFO, never WARN/BLOCKER, never created. Suppressed when the user has declined
    it (`snapshot_declined: true` in .docs-first/config.yml) — decisions, not re-asks.
    """

    if discover_mode(repo) != "alignment":
        return

    config = _dfc.load_config(repo)
    if config is not None and config.snapshot_declined:
        return

    if (repo / "docs" / "reports" / "CURRENT_STATE.md").exists():
        return

    make_finding(
        findings,
        "INFO",
        "CURRENT_STATE_SUGGESTED",
        "docs/reports/CURRENT_STATE.md",
        "Optional operational-state snapshot not present. Consider adopting the local, "
        "gitignored snapshot docs/reports/CURRENT_STATE.md (where you are, next action, deploy "
        "state; rewritten freely each session, never committed). To stop this suggestion, set "
        "snapshot_declined: true in .docs-first/config.yml.",
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


def audit_repository(repo: Path, diff_base: str | None = None) -> dict[str, Any]:
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
    check_feature_indexing(repo, findings)
    check_code_to_docs_coverage(repo, findings)
    check_unverified_claims(repo, findings)
    check_specs_outside_feature_docs(repo, findings)

    nfr_file = repo / "docs" / "nfr" / "NON_FUNCTIONAL.md"
    check_nfr_file(nfr_file, repo, findings)
    check_markdown_links(repo, findings)
    check_mkdocs_nav(repo, findings)
    check_index_map(repo, findings)
    check_ai_instruction_files(repo, findings)
    check_agent_profiles_config(repo, findings)
    check_enforcement_gates(repo, findings)
    check_current_state_suggestion(repo, findings)

    if diff_base is not None:
        check_diff_feature_docs(repo, findings, diff_base)

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
    parser.add_argument(
        "--diff",
        nargs="?",
        const=DEFAULT_DIFF_BASE,
        default=None,
        metavar="BASE",
        dest="diff_base",
        help=(
            "Also fail when the diff against BASE "
            f"(default {DEFAULT_DIFF_BASE}) touches code but no feature doc. "
            "Intended for PR CI."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo)

    result = audit_repository(repo, diff_base=args.diff_base)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(result))

    blockers = result["summary"]["blocker"]
    return 2 if blockers > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
