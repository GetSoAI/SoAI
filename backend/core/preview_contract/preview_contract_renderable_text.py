"""SoAI - Preview-contract renderable text normalization [backend/core/preview_contract/preview_contract_renderable_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.formatting.markdown_code_segments import (
    strip_fenced_code_blocks,
    strip_inline_code_spans,
)

__all__ = (
    "coerce_preview_contract_text_without_fenced_code_blocks",
    "coerce_renderable_preview_contract_text",
)


def coerce_preview_contract_text_without_fenced_code_blocks(text: str) -> str:
    normalized = str(text or "")
    if not normalized:
        return ""
    return strip_fenced_code_blocks(normalized)


def coerce_renderable_preview_contract_text(text: str) -> str:
    normalized = str(text or "")
    if not normalized:
        return ""
    without_fences = strip_fenced_code_blocks(normalized)
    return strip_inline_code_spans(without_fences)
