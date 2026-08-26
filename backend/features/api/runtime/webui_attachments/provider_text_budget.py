"""SoAI - WebUI provider text budget math [backend/features/api/runtime/webui_attachments/provider_text_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("resolve_provider_text_char_budget",)


def resolve_provider_text_char_budget(
    *,
    context_window_tokens: int | None,
    doc_part_count: int,
    fraction: float,
    char_to_token_ratio: int,
    floor_chars: int,
    ceiling_chars: int,
    reserved_output_tokens: int,
) -> int:
    count = max(doc_part_count, 1)
    if context_window_tokens is None:
        return min(max(floor_chars, 1), ceiling_chars)

    usable_tokens = max(context_window_tokens - reserved_output_tokens, 1)
    aggregate_chars = max(int(usable_tokens * fraction * char_to_token_ratio), 1)
    per_doc_chars = max(aggregate_chars // count, 1)
    if aggregate_chars >= floor_chars * count:
        per_doc_chars = max(per_doc_chars, floor_chars)
    return min(max(per_doc_chars, 1), ceiling_chars)
