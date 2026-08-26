"""SoAI - Provider-safe Messaging text chunking [backend/core/messaging/delivery_chunking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import regex

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform

__all__ = ("MessagingChunkPlan", "plan_messaging_text_chunks")


@dataclass(frozen=True, slots=True)
class MessagingChunkPlan:
    chunks: tuple[str, ...]
    failure_code: str | None


def _provider_text_limit(platform: MessagingPlatform) -> int:
    if platform == "discord":
        return 2000
    return 4096


def _preferred_split_index(parts: list[str]) -> int | None:
    preferred_index: int | None = None
    for index, part in enumerate(parts, start=1):
        if part.isspace():
            preferred_index = index
    return preferred_index


def _bounded_grapheme_parts(grapheme: str, limit: int) -> tuple[str, ...]:
    if len(grapheme) <= limit:
        return (grapheme,)
    return tuple(grapheme[start : start + limit] for start in range(0, len(grapheme), limit))


def plan_messaging_text_chunks(
    platform: MessagingPlatform,
    content_text: str,
) -> MessagingChunkPlan:
    limit = _provider_text_limit(platform)
    if not content_text:
        return MessagingChunkPlan(chunks=(), failure_code="delivery_content_empty")
    chunks: list[str] = []
    pending_parts: list[str] = []
    pending_length = 0
    preferred_index: int | None = None
    for match in regex.finditer(r"\X", content_text):
        for part in _bounded_grapheme_parts(match.group(0), limit):
            while pending_parts and pending_length + len(part) > limit:
                split_index = preferred_index or len(pending_parts)
                chunks.append("".join(pending_parts[:split_index]))
                pending_parts = pending_parts[split_index:]
                pending_length = sum(len(value) for value in pending_parts)
                preferred_index = _preferred_split_index(pending_parts)
            pending_parts.append(part)
            pending_length += len(part)
            if part.isspace():
                preferred_index = len(pending_parts)
    if pending_parts:
        chunks.append("".join(pending_parts))
    return MessagingChunkPlan(chunks=tuple(chunks), failure_code=None)
