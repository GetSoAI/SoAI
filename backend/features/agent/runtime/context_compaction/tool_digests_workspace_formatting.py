"""SoAI - Files-root tool digest formatting helpers [backend/features/agent/runtime/context_compaction/tool_digests_workspace_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import coerce_exact_int_or_none
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.context_compaction.internal_protocols import (
    TruncateLineProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TruncateLineProtocol",
    "coerce_bool",
    "coerce_int",
    "digest_code_diffs",
    "summarize_paths",
)


def coerce_bool(value: JSONValue) -> bool | None:
    return value if isinstance(value, bool) else None


def coerce_int(value: JSONValue) -> int | None:
    return coerce_exact_int_or_none(value)


def summarize_paths(
    paths: list[str],
    *,
    label: str,
    sample: int,
    truncate_line: TruncateLineProtocol,
) -> str:
    if not paths:
        return f"{label}=0"
    kept = [path for path in paths[:sample] if path]
    suffix = "…" if len(paths) > len(kept) else ""
    preview = ", ".join(truncate_line(path, max_chars=80) for path in kept)
    return f"{label}={len(paths)} [{preview}{suffix}]"


def digest_code_diffs(
    tool_result: JSONDict,
    *,
    truncate_line: TruncateLineProtocol,
) -> list[str]:
    diffs = tool_result.get("code_diffs")
    if not isinstance(diffs, list) or not diffs:
        return []
    touched: set[str] = set()
    for entry in diffs:
        if not isinstance(entry, dict):
            continue
        path = coerce_optional_trimmed_str(entry.get("path"))
        if path:
            touched.add(path)
    if not touched:
        return []
    return [
        f"touched: {summarize_paths(sorted(touched), label='files', sample=10, truncate_line=truncate_line)}",
    ]
