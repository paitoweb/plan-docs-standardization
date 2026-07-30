#!/usr/bin/env python3
"""Read/write the .docs-first/config.yml state file.

Stdlib-only on purpose: the local git hook and CI must parse this with bare
python3, so we use a tiny flat-YAML subset (scalars + inline lists) rather than
depending on PyYAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CONFIG_REL = ".docs-first/config.yml"
SCHEMA_VERSION = 1


@dataclass
class DocsFirstConfig:
    profiles: list[str] = field(default_factory=list)
    enforcement_chosen: list[str] = field(default_factory=list)
    enforcement_declined: list[str] = field(default_factory=list)
    snapshot_declined: bool = False
    # --diff mode only. Paths matching these globs never count as code (build output,
    # lockfiles, generated clients), and these extensions define what "code" means.
    diff_exempt_globs: list[str] = field(default_factory=list)
    code_extensions: list[str] = field(default_factory=list)
    # Code-to-docs coverage. feature_map entries are "path=slug" strings rather than a
    # nested mapping: the parser below must stay trivial (see _parse_value), so a flat
    # inline list is the only shape available.
    feature_map: list[str] = field(default_factory=list)
    code_roots: list[str] = field(default_factory=list)
    coverage_gate: bool = False
    coverage_min: int | None = None
    updated: str | None = None
    version: int = SCHEMA_VERSION


def _fmt_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def render_config(cfg: DocsFirstConfig) -> str:
    lines = [
        "# Managed by plan-docs-standardization. Records decisions, not observations.",
        f"version: {cfg.version}",
        f"profiles: {_fmt_list(cfg.profiles)}",
        f"enforcement_chosen: {_fmt_list(cfg.enforcement_chosen)}",
        f"enforcement_declined: {_fmt_list(cfg.enforcement_declined)}",
    ]
    if cfg.snapshot_declined:
        lines.append("snapshot_declined: true")
    if cfg.diff_exempt_globs:
        lines.append(f"diff_exempt_globs: {_fmt_list(cfg.diff_exempt_globs)}")
    if cfg.code_extensions:
        lines.append(f"code_extensions: {_fmt_list(cfg.code_extensions)}")
    if cfg.feature_map:
        lines.append(f"feature_map: {_fmt_list(cfg.feature_map)}")
    if cfg.code_roots:
        lines.append(f"code_roots: {_fmt_list(cfg.code_roots)}")
    if cfg.coverage_gate:
        lines.append("coverage_gate: true")
    if cfg.coverage_min is not None:
        lines.append(f"coverage_min: {cfg.coverage_min}")
    if cfg.updated is not None:
        lines.append(f"updated: {cfg.updated}")
    return "\n".join(lines) + "\n"


def _parse_value(raw: str) -> object:
    # Value space is intentionally narrow: inline lists of bare tokens (profile/gate
    # keys, which never contain commas) plus scalar strings/ints. Quoted items
    # containing commas are not supported — the parser must stay trivial and crash-free
    # because it feeds the CI/pre-commit gate.
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    if raw.isdigit():
        return int(raw)
    return raw.strip("\"'")


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _coerce_optional_int(value: object) -> int | None:
    """None when the key is absent or unparseable; the caller then uses its own default."""

    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_feature_map(entries: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Split "path=slug" entries into (pairs, malformed).

    Flat "path=slug" rather than a nested mapping because _parse_value must stay trivial:
    the pre-commit hook and CI parse this file with bare python3, no PyYAML.
    """

    pairs: list[tuple[str, str]] = []
    malformed: list[str] = []
    for entry in entries:
        path, separator, slug = entry.partition("=")
        path, slug = path.strip(), slug.strip()
        if not separator or not path or not slug:
            malformed.append(entry)
            continue
        pairs.append((path, slug))
    return pairs, malformed


def parse_config(text: str) -> DocsFirstConfig:
    data: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        data[key.strip()] = _parse_value(value)

    return DocsFirstConfig(
        profiles=list(data.get("profiles", []) or []),
        enforcement_chosen=list(data.get("enforcement_chosen", []) or []),
        enforcement_declined=list(data.get("enforcement_declined", []) or []),
        snapshot_declined=_coerce_bool(data.get("snapshot_declined", False), False),
        diff_exempt_globs=list(data.get("diff_exempt_globs", []) or []),
        code_extensions=list(data.get("code_extensions", []) or []),
        feature_map=list(data.get("feature_map", []) or []),
        code_roots=list(data.get("code_roots", []) or []),
        coverage_gate=_coerce_bool(data.get("coverage_gate", False), False),
        coverage_min=_coerce_optional_int(data.get("coverage_min")),
        updated=(data.get("updated") or None),
        version=_coerce_int(data.get("version", SCHEMA_VERSION), SCHEMA_VERSION),
    )


def load_config(repo: Path) -> DocsFirstConfig | None:
    path = Path(repo) / CONFIG_REL
    if not path.exists():
        return None
    return parse_config(path.read_text(encoding="utf-8"))


def save_config(repo: Path, cfg: DocsFirstConfig) -> Path:
    """Write .docs-first/config.yml. Mutating — callers must have user consent."""

    path = Path(repo) / CONFIG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config(cfg), encoding="utf-8")
    return path
