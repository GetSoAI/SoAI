"""SoAI - Active conversation stream status route [backend/features/api/routes/webui/conversation_stream_status_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, is_json_value
from features.api.routes.webui.conversation_stream_admission import (
    resolve_conversation_stream_admission,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.conversations import ConversationStreamStatusResponse
from features.api.schemas.json_fields import PydanticJSONValue
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.status_preview_constants import (
    STATUS_PREVIEW_START_COOLDOWN_MS,
)
from features.chat.interaction_tasks import list_pending_conversation_interaction_payloads

__all__ = ("register_routes",)


def resolve_stream_status_conversation_id(conversation_record: JSONDict, conv_id: str) -> str:
    record_id = conversation_record.get("id")
    if isinstance(record_id, str) and record_id.strip():
        return record_id.strip()
    normalized_conv_id = conv_id.strip()
    if normalized_conv_id:
        return normalized_conv_id
    raise ValidationError("Conversation stream status requires a valid conversation id.")


def resolve_active_tool_call_count(runtime: AssistantTimelineRuntime) -> int:
    pending_call_ids: set[str] = set()
    if runtime.pending_tool_events is not None:
        for pending_event in runtime.pending_tool_events:
            call_id = pending_event.tool_payload.get("call_id")
            if isinstance(call_id, str) and call_id.strip():
                pending_call_ids.add(call_id.strip())
    active_call_ids = (
        set(runtime.running_tool_call_ids) | set(runtime.started_tool_call_ids) | pending_call_ids
    )
    active_call_ids.difference_update(set(runtime.completed_tool_call_ids))
    return len(active_call_ids)


def normalize_stream_status_preview_args(
    value: JSONDict | None,
) -> dict[str, PydanticJSONValue] | None:
    if value is None:
        return None
    normalized: dict[str, PydanticJSONValue] = {}
    for key, item in value.items():
        if not key.strip() or not is_json_value(item):
            raise ValidationError("Stream status preview arguments must be a JSON object.")
        normalized[key] = item
    return normalized


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}/stream-status")
    async def get_conversation_stream_status(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversation_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_conversations.get_conversation(
                conv_id,
                current_user["id"],
            ),
            message="Conversation not found.",
        )
        if not isinstance(conversation_record, dict):
            raise ValidationError("Conversation record must be a mapping.")
        conversation_id = resolve_stream_status_conversation_id(
            dict(conversation_record),
            conv_id,
        )
        snapshot = await api_context.dependencies.chat_stream_registry.snapshot(
            user_id=current_user["id"],
            conv_id=conversation_id,
        )
        pending_interactions = await list_pending_conversation_interaction_payloads(
            api_context,
            conv_id=conversation_id,
            user_id=current_user["id"],
        )
        active_input_summary = (
            await api_context.dependencies.database_input_queue.summarize_active_inputs(
                conv_id=conversation_id,
                user_id=current_user["id"],
            )
        )
        admission = resolve_conversation_stream_admission(
            snapshot,
            active_input_summary=active_input_summary,
            user_interaction_pending=bool(pending_interactions),
        )
        runtime = snapshot.runtime
        if runtime is None:
            response = ConversationStreamStatusResponse(
                active=False,
                conversation_id=conversation_id,
                start_admission=admission.start_admission,
                stream_lifecycle=admission.stream_lifecycle,
                can_accept_conversation_input=admission.can_accept_conversation_input,
                can_start_next_prompt=admission.can_start_next_prompt,
                can_accept_steer_prompt=admission.can_accept_steer_prompt,
                active_tool_call_count=0,
            )
            return JSONResponse(content=response.model_dump())
        lock = ensure_chat_stream_publish_lock(runtime)
        async with lock:
            if runtime.terminal_persistence_completed:
                response = ConversationStreamStatusResponse(
                    active=False,
                    conversation_id=conversation_id,
                    start_admission=admission.start_admission,
                    stream_lifecycle=admission.stream_lifecycle,
                    can_accept_conversation_input=admission.can_accept_conversation_input,
                    can_start_next_prompt=admission.can_start_next_prompt,
                    can_accept_steer_prompt=admission.can_accept_steer_prompt,
                    active_tool_call_count=0,
                )
                return JSONResponse(content=response.model_dump())
            response = ConversationStreamStatusResponse(
                active=True,
                conversation_id=runtime.conv_id,
                start_admission=admission.start_admission,
                stream_lifecycle=admission.stream_lifecycle,
                can_accept_conversation_input=admission.can_accept_conversation_input,
                can_start_next_prompt=admission.can_start_next_prompt,
                can_accept_steer_prompt=admission.can_accept_steer_prompt,
                active_tool_call_count=resolve_active_tool_call_count(runtime),
                request_id=runtime.request_id,
                assistant_at_ms=runtime.assistant_at_ms,
                assistant_turn_at_ms=runtime.assistant_turn_at_ms,
                model_variant_index=runtime.model_variant_index,
                model_id=runtime.model_id,
                preview_key=runtime.status_preview_last_key,
                preview_args=normalize_stream_status_preview_args(runtime.status_preview_last_args),
                preview_generated_at_ms=(
                    runtime.status_preview_last_generated_at_ms
                    if runtime.status_preview_last_generated_at_ms > 0
                    else None
                ),
                preview_cooldown_ms=(
                    STATUS_PREVIEW_START_COOLDOWN_MS
                    if runtime.status_preview_last_key is not None
                    else None
                ),
                preview_trigger=runtime.status_preview_last_trigger,
            )
        return JSONResponse(content=response.model_dump())
