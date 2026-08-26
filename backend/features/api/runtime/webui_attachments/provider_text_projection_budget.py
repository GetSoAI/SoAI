"""SoAI - WebUI attachment projection text budget resolution [backend/features/api/runtime/webui_attachments/provider_text_projection_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.message_content_parts import iter_message_content_parts
from features.api.runtime.webui_attachments.provider_text_budget import (
    resolve_provider_text_char_budget,
)
from features.api.runtime.webui_attachments.provider_text_settings import (
    read_provider_text_settings,
)
from features.openai.model_context_resolution import (
    resolve_context_window_tokens_for_request_model,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.webui_attachments.projection_context import (
        SoaiPathToolAccess,
    )

__all__ = (
    "count_inline_text_attachment_parts",
    "resolve_provider_text_char_budget_for_projection",
)

_INLINE_ATTACHMENT_TYPES = frozenset(("soai_file", "soai_path"))


def count_inline_text_attachment_parts(
    messages: list[JSONDict],
    *,
    vision_supported: bool,
    soai_path_tool_access: SoaiPathToolAccess | None,
) -> int:
    count = 0
    for part in iter_message_content_parts(messages):
        part_type = part.get("type")
        if part_type not in _INLINE_ATTACHMENT_TYPES:
            continue
        if vision_supported and part.get("preview_type") == "video":
            count += 1
            continue
        if part_type == "soai_path" and soai_path_tool_access is not None:
            entry_type = part.get("entry_type")
            if entry_type == "file" and soai_path_tool_access.can_read_files:
                continue
            if entry_type == "folder" and soai_path_tool_access.can_list_folders:
                continue
        if vision_supported and part.get("preview_type") == "image" and part_type != "soai_file":
            continue
        count += 1
    return count


async def resolve_provider_text_char_budget_for_projection(
    *,
    dependencies: ApiDependencies,
    model_id: str | None,
    messages: list[JSONDict],
    vision_supported: bool,
    soai_path_tool_access: SoaiPathToolAccess | None,
) -> int:
    settings = read_provider_text_settings(dependencies.config)
    doc_part_count = count_inline_text_attachment_parts(
        messages,
        vision_supported=vision_supported,
        soai_path_tool_access=soai_path_tool_access,
    )
    if doc_part_count == 0:
        return settings.min_chars
    context_window_tokens: int | None = None
    if model_id is not None:
        context_window_tokens = await resolve_context_window_tokens_for_request_model(
            model_name=model_id,
            model_resolution_service=dependencies.model_resolution_service,
            model_information_service=dependencies.model_information_service,
            virtual_model_get=dependencies.model_virtual_model_service.virtual_model_get,
        )
    return resolve_provider_text_char_budget(
        context_window_tokens=context_window_tokens,
        doc_part_count=doc_part_count,
        fraction=settings.context_fraction,
        char_to_token_ratio=settings.char_to_token_ratio,
        floor_chars=settings.min_chars,
        ceiling_chars=settings.max_store_chars,
        reserved_output_tokens=settings.reserved_output_tokens,
    )
