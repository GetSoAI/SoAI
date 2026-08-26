"""SoAI - Shared compaction text normalization helpers [backend/features/agent/runtime/context_compaction/text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("truncate_compaction_line",)


def truncate_compaction_line(text: str, *, max_chars: int = 240) -> str:
    normalized = " ".join(str(text or "").strip().split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}…"
