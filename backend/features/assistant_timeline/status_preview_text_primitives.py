"""SoAI - Status preview text primitives [backend/features/assistant_timeline/status_preview_text_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("collapse_status_preview_whitespace",)


def collapse_status_preview_whitespace(value: str, *, max_chars: int) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= 1:
        return normalized[:max_chars]
    return f"{normalized[: max_chars - 1].rstrip()}…"
