"""SoAI - Context compaction tag-block helpers [backend/features/agent/runtime/context_compaction/tag_blocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("extract_tag_block_text",)


def extract_tag_block_text(
    content: str,
    *,
    open_tag: str,
    close_tag: str,
) -> str | None:
    open_index = content.find(open_tag)
    if open_index < 0:
        return None
    close_index = content.find(close_tag, open_index + len(open_tag))
    if close_index < 0:
        return None
    extracted = content[open_index + len(open_tag) : close_index].strip()
    return extracted or None
