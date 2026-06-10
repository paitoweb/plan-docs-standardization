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
    if cfg.updated is not None:
        lines.append(f"updated: {cfg.updated}")
    return "\n".join(lines) + "\n"


def _parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    if raw.isdigit():
        return int(raw)
    return raw.strip("\"'")


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
        updated=(data.get("updated") or None),
        version=int(data.get("version", SCHEMA_VERSION)),
    )


def load_config(repo: Path) -> DocsFirstConfig | None:
    path = Path(repo) / CONFIG_REL
    if not path.exists():
        return None
    return parse_config(path.read_text(encoding="utf-8"))
