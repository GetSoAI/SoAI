"""SoAI - Chat usage-preview model-visible prompt projection [backend/features/api/runtime/chat_usage_preview_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.request_fields import resolve_optional_model_name
from core.openai.stream_request_preparation import (
    OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
    build_openai_stream_request_json,
)
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.timing.epoch import epoch_ms
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries,
)
from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
from core.tool_calls.tool_result_prompt_history import shape_prompt_history_tool_results
from core.workspaces.soai_path_link_codec import strip_soai_path_tokens
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.api.runtime.request_user_resolution import resolve_request_user_id
from features.api.runtime.soai_links.content_parts import (
    message_content_from_text_and_attachments,
)
from features.api.runtime.tool_request.preparation import prepare_mcp_tools_for_request
from features.api.runtime.webui_attachments.provider_projection import (
    build_webui_attachment_provider_projector,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "PreparedChatUsagePreviewRequest",
    "build_chat_usage_preview_messages",
    "prepare_chat_usage_preview_request",
)


@dataclass(frozen=True, slots=True)
class PreparedChatUsagePreviewRequest:
    inference_request_json: JSONDict


def _require_request_model(inference_request_json: JSONDict) -> None:
    if resolve_optional_model_name(inference_request_json) is None:
        raise ValidationError("Chat usage preview requires a resolved model.")


def build_chat_usage_preview_messages(
    *,
    canonical_history: list[JSONDict],
    draft_user_text: str | None,
    draft_attachment_content: list[JSONValue] | None = None,
) -> list[JSONDict]:
    resolution = resolve_context_compaction_boundaries(
        canonical_history,
        strip_leading_pinned_prefix=True,
    )
    messages = resolution.messages
    messages = shape_prompt_history_tool_results(
        messages,
        shape_cache=ToolResultPromptShapeCache(),
    )
    draft_content = _build_draft_content(
        draft_user_text=draft_user_text,
        draft_attachment_content=draft_attachment_content or [],
    )
    if draft_content is None:
        return messages
    messages.append({"role": "user", "content": draft_content})
    return messages


def _build_draft_content(
    *,
    draft_user_text: str | None,
    draft_attachment_content: list[JSONValue],
) -> list[JSONDict] | None:
    projected_draft_user_text = (
        strip_soai_path_tokens(draft_user_text) if draft_user_text is not None else None
    )
    if not draft_attachment_content and (
        projected_draft_user_text is None or not projected_draft_user_text.strip()
    ):
        return None
    return message_content_from_text_and_attachments(
        projected_draft_user_text,
        draft_attachment_content,
    )


async def prepare_chat_usage_preview_request(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    openai_request: JSONDict,
    conv_id: str,
    canonical_history: list[JSONDict],
    draft_user_text: str | None,
    draft_attachment_content: list[JSONValue] | None = None,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> PreparedChatUsagePreviewRequest:
    now_ms = int(epoch_ms())
    forbidden_fields = OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES
    request_json = build_openai_stream_request_json(
        openai_request=openai_request,
        logger=logger,
        trace_id=trace_id,
        forbidden_fields=forbidden_fields,
        conv_id=conv_id,
        messages=None,
    )
    canonical_prompt_messages = build_chat_usage_preview_messages(
        canonical_history=canonical_history,
        draft_user_text=draft_user_text,
        draft_attachment_content=draft_attachment_content,
    )
    user_id = resolve_request_user_id(request)

    project_agentic_prompt_messages = build_webui_attachment_provider_projector(
        dependencies=api_context.dependencies,
        conv_id=conv_id,
        user_id=user_id,
        model_id=resolve_optional_model_name(request_json),
    )

    messages = await project_agentic_prompt_messages(canonical_prompt_messages)
    request_json["messages"] = messages
    token_count_context = clone_request_context(request.state.context)
    prepared_request = await prepare_mcp_tools_for_request(
        request=request,
        api_context=api_context,
        request_json=request_json,
        context=token_count_context,
        request_source=REQUEST_SOURCE_WEBUI_WS,
        message_index=len(messages),
        assistant_at_ms=now_ms,
        assistant_turn_at_ms=now_ms,
        model_variant_index=0,
        knowledge_prompt_mode="projection",
        agentic_message_source=AgenticRequestMessageSource(
            canonical_messages=canonical_prompt_messages,
            provider_projector=project_agentic_prompt_messages,
        ),
    )
    inference_request_json = (
        dict(prepared_request.prepared_agent_request.final_payload)
        if prepared_request.prepared_agent_request is not None
        else build_inference_request_payload(prepared_request.request_json)
    )
    _require_request_model(inference_request_json)
    return PreparedChatUsagePreviewRequest(
        inference_request_json=inference_request_json,
    )
