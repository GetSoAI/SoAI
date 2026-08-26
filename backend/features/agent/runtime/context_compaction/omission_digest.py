"""SoAI - Omitted message digest rendering for compaction [backend/features/agent/runtime/context_compaction/omission_digest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.runtime.context_compaction.digest import digest_compaction_unit
from features.agent.runtime.context_compaction.history import (
    take_oldest_compaction_unit,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("render_omitted_messages_digest",)

_DEFAULT_SAMPLE_MESSAGES: int = 200
_DEFAULT_MAX_LINES: int = 32
_DEFAULT_MAX_CHARS: int = 2000


def render_omitted_messages_digest(
    *,
    dropped: list[JSONDict],
    omitted_count: int,
    sample_messages: int = _DEFAULT_SAMPLE_MESSAGES,
    max_lines: int = _DEFAULT_MAX_LINES,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str | None:
    if omitted_count <= 0:
        return None
    resolved_sample_messages = max(0, int(sample_messages))
    resolved_max_lines = max(1, int(max_lines))
    resolved_max_chars = max(1, int(max_chars))
    sample = dropped[-resolved_sample_messages:] if dropped and resolved_sample_messages > 0 else []
    remaining = list(sample)
    raw_lines: list[str] = []
    while remaining:
        unit, remaining = take_oldest_compaction_unit(remaining)
        if not unit:
            break
        raw_lines.extend(digest_compaction_unit(unit))
        if len(raw_lines) > 256:
            raw_lines = raw_lines[-256:]
    header_line = f"omitted_messages={int(omitted_count)}"
    selected: list[str] = []
    total_chars = len(header_line) + 2
    line_budget = resolved_max_lines - 1
    for line in reversed(raw_lines):
        normalized = str(line or "").strip()
        if not normalized:
            continue
        if len(selected) >= line_budget:
            break
        added = len(normalized) + 2
        if total_chars + added > resolved_max_chars:
            break
        selected.append(normalized)
        total_chars += added
    rendered = ["STATE:", f"- {header_line}"]
    rendered.extend([f"- {entry}" for entry in reversed(selected)])
    return "\n".join(rendered).strip() or None
