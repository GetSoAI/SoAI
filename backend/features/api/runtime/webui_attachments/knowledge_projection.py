"""SoAI - Provider-safe knowledge attachment projection [backend/features/api/runtime/webui_attachments/knowledge_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import (
    content_part_from_knowledge_summary,
)
from core.attachments.attachment_content_validation import (
    validate_soai_knowledge_content_part,
)
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    coerce_non_negative_int_strict_or_zero,
    coerce_optional_non_negative_int_strict,
)
from features.api.runtime.webui_attachments.provider_text_rendering import (
    sanitize_provider_text_field,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = ("project_soai_knowledge_for_provider",)

_LIVE_DOCUMENT_OPERATION_TYPES = frozenset(("added", "reindexed", "updated"))
_LIVE_SOURCE_PAGE_LIMIT = 100


def _safe(value: JSONValue, fallback: str) -> str:
    if isinstance(value, str):
        sanitized = sanitize_provider_text_field(value)
        if sanitized is not None:
            return sanitized
    return fallback


def _count_text(part: JSONDict, field_name: str) -> str:
    return str(coerce_non_negative_int_strict_or_zero(part.get(field_name)))


def _status_counts_text(part: JSONDict) -> str:
    value = part.get("status_counts")
    if not isinstance(value, dict):
        return ""
    entries: list[str] = []
    for status, count in sorted(value.items()):
        if not isinstance(status, str):
            continue
        sanitized_status = sanitize_provider_text_field(status)
        if sanitized_status is None:
            continue
        if not is_strict_int(count):
            continue
        entries.append(f"{sanitized_status}={coerce_non_negative_int_strict_or_zero(count)}")
    if not entries:
        return ""
    return f"; statuses={', '.join(entries)}"


def knowledge_reference_text(part: JSONDict) -> str:
    canonical = validate_soai_knowledge_content_part(part)
    title = _safe(canonical.get("title"), "Knowledge")
    operation_type = _safe(canonical.get("operation_type"), "updated")
    source_type = _safe(canonical.get("source_type"), "knowledge")
    return (
        f"Knowledge attached: {title}; operation={operation_type}; source={source_type}; "
        f"total={_count_text(canonical, 'total_count')}; "
        f"visible={_count_text(canonical, 'visible_count')}; "
        f"hidden={_count_text(canonical, 'hidden_count')}"
        f"{_status_counts_text(canonical)}."
    )


def _unavailable_text(part: JSONDict, *, reason: str) -> str:
    title = _safe(part.get("title"), "Knowledge")
    sanitized_reason = sanitize_provider_text_field(reason) or "Knowledge is unavailable."
    return f"Knowledge unavailable: {title}; {sanitized_reason}"


def _metadata_matches_part(part: JSONDict, summary: JSONDict) -> bool:
    if summary.get("state") != "committed":
        return False
    try:
        summary_part = content_part_from_knowledge_summary(summary)
    except (KeyError, TypeError, ValidationError, ValueError):
        return False
    return summary_part == part


def _requires_live_document_source(part: JSONDict) -> bool:
    return (
        part.get("source_type") != "linked_knowledge"
        and part.get("operation_type") in _LIVE_DOCUMENT_OPERATION_TYPES
    )


def _cursor_int(page: JSONDict, field_name: str) -> int | None:
    cursor = page.get("next_cursor")
    if not isinstance(cursor, dict):
        return None
    value = cursor.get(field_name)
    return coerce_optional_non_negative_int_strict(value)


async def _completed_document_is_live(
    context: WebuiAttachmentProjectionContext,
    *,
    document_id: str,
) -> bool:
    document = await context.dependencies.database_files.get_rag_document_by_id(document_id)
    if document is None:
        return False
    return (
        document["status"] == "completed"
        and document["conv_id"] == context.conv_id
        and document["user_id"] == context.user_id
    )


async def _has_live_completed_source(
    context: WebuiAttachmentProjectionContext,
    *,
    knowledge_attachment_id: str,
) -> bool:
    cursor_item_index: int | None = None
    cursor_id: int | None = None
    while True:
        page = await context.dependencies.database_conversation_knowledge_attachments.get_knowledge_attachment_items_page(
            conv_id=context.conv_id,
            user_id=context.user_id,
            knowledge_attachment_id=knowledge_attachment_id,
            limit=_LIVE_SOURCE_PAGE_LIMIT,
            cursor_item_index=cursor_item_index,
            cursor_id=cursor_id,
            status="completed",
            query=None,
        )
        if page is None:
            return False
        items = page.get("items")
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                return False
            document_id = item.get("document_id")
            if not isinstance(document_id, str) or not document_id.strip():
                continue
            if item.get("operation_type") not in _LIVE_DOCUMENT_OPERATION_TYPES:
                continue
            if await _completed_document_is_live(context, document_id=document_id):
                return True
        cursor_item_index = _cursor_int(page, "item_index")
        cursor_id = _cursor_int(page, "id")
        if cursor_item_index is None or cursor_id is None:
            return False


async def project_soai_knowledge_for_provider(
    context: WebuiAttachmentProjectionContext,
    *,
    part: JSONDict,
) -> list[JSONDict]:
    canonical = validate_soai_knowledge_content_part(part)
    knowledge_attachment_id = str(canonical.get("knowledge_attachment_id") or "")
    if not knowledge_attachment_id:
        return [
            {
                "type": "text",
                "text": _unavailable_text(canonical, reason="Knowledge attachment is unavailable."),
            },
        ]
    summary = await context.dependencies.database_conversation_knowledge_attachments.get_knowledge_attachment(
        conv_id=context.conv_id,
        user_id=context.user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if summary is None or not _metadata_matches_part(canonical, summary):
        return [
            {
                "type": "text",
                "text": _unavailable_text(canonical, reason="Knowledge attachment is unavailable."),
            },
        ]
    if _requires_live_document_source(canonical) and not await _has_live_completed_source(
        context,
        knowledge_attachment_id=knowledge_attachment_id,
    ):
        return [
            {
                "type": "text",
                "text": _unavailable_text(canonical, reason="Knowledge source is unavailable."),
            },
        ]
    return [{"type": "text", "text": knowledge_reference_text(canonical)}]
