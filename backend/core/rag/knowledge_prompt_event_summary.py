"""SoAI - Knowledge prompt event summaries [backend/core/rag/knowledge_prompt_event_summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.rag.knowledge_prompt_contract import (
    KNOWLEDGE_PROMPT_MAX_DOCUMENT_NAMES_PER_EVENT,
    KNOWLEDGE_PROMPT_MAX_VISIBLE_NAME_CHARS,
)
from core.rag.knowledge_prompt_types import KnowledgePromptEventRecord

__all__ = (
    "coalesce_knowledge_prompt_reindex_events",
    "format_knowledge_prompt_event_lines",
    "truncate_knowledge_prompt_name",
)


def coalesce_knowledge_prompt_reindex_events(
    events: tuple[KnowledgePromptEventRecord, ...],
) -> tuple[KnowledgePromptEventRecord, ...]:
    terminal_types = {
        "knowledge_reindex_completed",
        "knowledge_reindex_failed",
        "knowledge_reindex_cancelled",
    }
    terminal_task_ids = {
        task_id
        for event in events
        if event.event_type in terminal_types
        for task_id in (_event_task_id(event),)
        if task_id is not None
    }
    if not terminal_task_ids:
        return events
    return tuple(
        event
        for event in events
        if event.event_type != "knowledge_reindex_queued"
        or _event_task_id(event) not in terminal_task_ids
    )


def format_knowledge_prompt_event_lines(events: tuple[KnowledgePromptEventRecord, ...]) -> str:
    rendered = [_format_event(event) for event in events]
    return "; ".join(line for line in rendered if line)


def truncate_knowledge_prompt_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if len(normalized) <= KNOWLEDGE_PROMPT_MAX_VISIBLE_NAME_CHARS:
        return normalized
    return f"{normalized[: KNOWLEDGE_PROMPT_MAX_VISIBLE_NAME_CHARS - 3].rstrip()}..."


def _event_task_id(event: KnowledgePromptEventRecord) -> str | None:
    value = event.details.get("task_id")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _format_event(event: KnowledgePromptEventRecord) -> str:
    names = _format_names(event.document_names)
    suffix = f" ({names})" if names else ""
    return f"{event.event_type.replace('_', ' ')}{suffix}"


def _format_names(names: tuple[str, ...]) -> str:
    visible = [
        truncate_knowledge_prompt_name(name)
        for name in names[:KNOWLEDGE_PROMPT_MAX_DOCUMENT_NAMES_PER_EVENT]
    ]
    omitted_count = max(0, len(names) - len(visible))
    if omitted_count:
        visible.append(f"{omitted_count} more")
    return ", ".join(visible)
