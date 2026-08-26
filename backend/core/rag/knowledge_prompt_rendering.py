"""SoAI - Knowledge prompt rendering [backend/core/rag/knowledge_prompt_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.rag.knowledge_prompt_contract import (
    KNOWLEDGE_ACCESS_TOOL_NAMES,
    KNOWLEDGE_MANAGEMENT_TOOL_NAMES,
    KNOWLEDGE_PROMPT_ENABLE_TOOLS_GUIDANCE,
    KNOWLEDGE_PROMPT_MAX_BODY_CHARS,
    KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE,
)
from core.rag.knowledge_prompt_event_summary import (
    coalesce_knowledge_prompt_reindex_events,
    format_knowledge_prompt_event_lines,
    truncate_knowledge_prompt_name,
)
from core.rag.knowledge_prompt_types import (
    KnowledgePromptEventRecord,
    KnowledgePromptProjectionInputs,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from core.validation.integers import is_strict_int

__all__ = ("KnowledgePromptRenderResult", "render_knowledge_prompt")


@dataclass(frozen=True, slots=True)
class KnowledgePromptRenderResult:
    system_message: str | None
    state_signature: str
    event_ceiling_id: int
    missing_required_tools: tuple[str, ...]
    visible_knowledge_tools: tuple[str, ...]


def render_knowledge_prompt(
    *,
    inputs: KnowledgePromptProjectionInputs,
    visible_tool_names: tuple[str, ...],
    model_supports_tools: bool,
) -> KnowledgePromptRenderResult:
    visible_knowledge_tools = tuple(
        tool_name
        for tool_name in (*KNOWLEDGE_ACCESS_TOOL_NAMES, *KNOWLEDGE_MANAGEMENT_TOOL_NAMES)
        if tool_name in visible_tool_names
    )
    missing_required_tools = tuple(
        tool_name
        for tool_name in KNOWLEDGE_ACCESS_TOOL_NAMES
        if tool_name not in visible_tool_names
    )
    event_ceiling_id = _resolve_event_ceiling_id(inputs)
    state_signature = _build_state_signature(
        inputs=inputs,
        visible_knowledge_tools=visible_knowledge_tools,
        missing_required_tools=missing_required_tools,
        model_supports_tools=model_supports_tools,
    )
    pending_events = coalesce_knowledge_prompt_reindex_events(inputs.pending_events)
    document_count = _count(inputs.rag_counts, "document_count")
    if document_count <= 0 and not pending_events:
        return KnowledgePromptRenderResult(
            None,
            state_signature,
            event_ceiling_id,
            missing_required_tools,
            visible_knowledge_tools,
        )
    previous_signature = (
        inputs.delivery.last_delivered_state_signature if inputs.delivery is not None else None
    )
    if previous_signature == state_signature and not pending_events:
        return KnowledgePromptRenderResult(
            None,
            state_signature,
            event_ceiling_id,
            missing_required_tools,
            visible_knowledge_tools,
        )
    if document_count <= 0:
        message = _build_empty_change_prompt(pending_events)
    elif not model_supports_tools or missing_required_tools:
        message = _build_advisory_prompt(
            inputs=inputs,
            missing_required_tools=missing_required_tools,
            visible_knowledge_tools=visible_knowledge_tools,
            model_supports_tools=model_supports_tools,
        )
    else:
        message = _build_available_prompt(
            inputs=inputs,
            pending_events=pending_events,
            visible_knowledge_tools=visible_knowledge_tools,
        )
    return KnowledgePromptRenderResult(
        _truncate_body(message),
        state_signature,
        event_ceiling_id,
        missing_required_tools,
        visible_knowledge_tools,
    )


def _build_state_signature(
    *,
    inputs: KnowledgePromptProjectionInputs,
    visible_knowledge_tools: tuple[str, ...],
    missing_required_tools: tuple[str, ...],
    model_supports_tools: bool,
) -> str:
    payload: JSONDict = {
        "rag_config": inputs.rag_config or {},
        "rag_counts": inputs.rag_counts,
        "latest_documents": list(inputs.latest_documents),
        "visible_knowledge_tools": list(visible_knowledge_tools),
        "missing_required_tools": list(missing_required_tools),
        "model_supports_tools": model_supports_tools,
    }
    return serialize_json_compact_stable_strict(payload)


def _resolve_event_ceiling_id(inputs: KnowledgePromptProjectionInputs) -> int:
    highest_event_id = max((event.id for event in inputs.pending_events), default=0)
    if highest_event_id > 0:
        return highest_event_id
    if inputs.delivery is None:
        return 0
    return max(0, int(inputs.delivery.last_delivered_event_id))


def _build_empty_change_prompt(events: tuple[KnowledgePromptEventRecord, ...]) -> str:
    lines = [
        "Knowledge changed for this conversation.",
        "No Knowledge documents currently exist.",
    ]
    event_lines = format_knowledge_prompt_event_lines(events)
    if event_lines:
        lines.append(f"Recent Knowledge changes: {event_lines}")
    lines.append(f"To add Knowledge, {KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE}")
    return "\n".join(lines)


def _build_advisory_prompt(
    *,
    inputs: KnowledgePromptProjectionInputs,
    missing_required_tools: tuple[str, ...],
    visible_knowledge_tools: tuple[str, ...],
    model_supports_tools: bool,
) -> str:
    disabled_management_tools = tuple(
        tool_name
        for tool_name in KNOWLEDGE_MANAGEMENT_TOOL_NAMES
        if tool_name not in visible_knowledge_tools
    )
    lines = [
        "Knowledge documents exist for this conversation, but Knowledge cannot currently be used.",
        _format_counts(inputs.rag_counts),
    ]
    if not model_supports_tools:
        lines.append("The selected model cannot call tools.")
    if missing_required_tools:
        lines.append(f"Missing required Knowledge tools: {', '.join(missing_required_tools)}.")
    if disabled_management_tools:
        lines.append(f"Disabled management tools: {', '.join(disabled_management_tools)}.")
    lines.append(KNOWLEDGE_PROMPT_ENABLE_TOOLS_GUIDANCE)
    return "\n".join(lines)


def _build_available_prompt(
    *,
    inputs: KnowledgePromptProjectionInputs,
    pending_events: tuple[KnowledgePromptEventRecord, ...],
    visible_knowledge_tools: tuple[str, ...],
) -> str:
    lines = [
        "Knowledge exists for this conversation.",
        f"Visible Knowledge tools: {', '.join(visible_knowledge_tools)}.",
        _format_counts(inputs.rag_counts),
    ]
    event_lines = format_knowledge_prompt_event_lines(pending_events)
    if event_lines:
        lines.append(f"Recent Knowledge changes: {event_lines}")
    document_lines = _format_document_lines(inputs.latest_documents)
    if document_lines:
        lines.append(f"Recent Knowledge documents: {document_lines}")
    lines.append(
        "Use Knowledge tools when relevant, prefer knowledge_search first, and do not ask the user to remind you about Knowledge already available in this conversation.",
    )
    return "\n".join(lines)


def _format_counts(counts: JSONDict) -> str:
    return (
        "Knowledge counts: "
        f"total {_count(counts, 'document_count')}, completed {_count(counts, 'completed')}, "
        f"queued {_count(counts, 'queued')}, processing {_processing_count(counts)}, "
        f"error {_count(counts, 'error')}, searchable chunks {_count(counts, 'chunk_count')}."
    )


def _processing_count(counts: JSONDict) -> int:
    return sum(_count(counts, key) for key in ("fetching", "parsing", "chunking", "embedding"))


def _format_document_lines(documents: tuple[JSONDict, ...]) -> str:
    items: list[str] = []
    for document in documents:
        filename = document.get("filename")
        status = document.get("status")
        if not isinstance(filename, str) or not filename.strip():
            continue
        status_text = status.strip() if isinstance(status, str) and status.strip() else "unknown"
        items.append(f"{truncate_knowledge_prompt_name(filename)} [{status_text}]")
    return "; ".join(items)


def _truncate_body(message: str) -> str:
    if len(message) <= KNOWLEDGE_PROMPT_MAX_BODY_CHARS:
        return message
    return f"{message[: KNOWLEDGE_PROMPT_MAX_BODY_CHARS - 3].rstrip()}..."


def _count(counts: JSONDict, key: str) -> int:
    value = counts.get(key)
    return int(value) if is_strict_int(value) else 0
