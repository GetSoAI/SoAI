"""SoAI - Chat execution request routing resolution [backend/features/api/runtime/chat_execution/request_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.agent_mode import is_agent_mode
from core.events.types_models_requests import (
    EmbeddingRequestReceived,
    ImageGenerationRequestReceived,
    InferenceRequestReceived,
    TextToSpeechRequestReceived,
)
from core.runtime.ownership import resolve_http_owner_id
from core.tasks.type_catalog import (
    TASK_TYPE_BACKGROUND_JOB,
    TASK_TYPE_CHAT_COMPLETION,
    TASK_TYPE_EMBEDDING,
    TASK_TYPE_IMAGE_GENERATION,
    TASK_TYPE_TEXT_TO_SPEECH,
    TaskTypeId,
)
from features.api.runtime.context import ApiContext

if TYPE_CHECKING:
    from core.runtime.protocols import RequestOwnershipContextProtocol
    from core.types.json import JSONDict

__all__ = (
    "resolve_task_owner",
    "resolve_task_type",
    "should_use_async_accept",
)


def resolve_task_owner(
    context: RequestOwnershipContextProtocol,
    request_json: JSONDict,
) -> tuple[str, str]:
    default_owner_id = resolve_http_owner_id(context)
    try:
        mode_value = context.agent_mode
    except AttributeError:
        mode_value = None
    if not is_agent_mode(mode_value):
        return ("http_request", default_owner_id)
    conv_id = ""
    try:
        tool_context = context.mcp_tool_context
    except AttributeError:
        tool_context = None
    if tool_context is None:
        tool_conv_value = None
    else:
        try:
            tool_conv_value = tool_context.conv_id
        except AttributeError:
            tool_conv_value = None
    if isinstance(tool_conv_value, str):
        conv_id = tool_conv_value.strip()
    if not conv_id:
        request_conv_value = request_json.get("conv_id")
        if isinstance(request_conv_value, str):
            conv_id = request_conv_value.strip()
    if not conv_id:
        return ("http_request", default_owner_id)
    return ("conversation", conv_id)


def resolve_task_type(request_event_class: type[InferenceRequestReceived]) -> TaskTypeId:
    if request_event_class is InferenceRequestReceived:
        return TASK_TYPE_CHAT_COMPLETION
    if request_event_class is EmbeddingRequestReceived:
        return TASK_TYPE_EMBEDDING
    if request_event_class is ImageGenerationRequestReceived:
        return TASK_TYPE_IMAGE_GENERATION
    if request_event_class is TextToSpeechRequestReceived:
        return TASK_TYPE_TEXT_TO_SPEECH
    return TASK_TYPE_BACKGROUND_JOB


def should_use_async_accept(request: Request, api_context: ApiContext) -> bool:
    try:
        request_state = request.state
    except AttributeError:
        request_state = None
    if request_state is not None:
        try:
            force_sync_response = request_state.force_sync_response
        except AttributeError:
            force_sync_response = False
        if bool(force_sync_response):
            return False
    try:
        headers = request.headers
    except AttributeError:
        headers = None
    if headers is None:
        prefer_header = None
    else:
        try:
            prefer_header = headers.get("prefer")
        except AttributeError:
            prefer_header = None
    if isinstance(prefer_header, str):
        for token in prefer_header.split(","):
            if token.strip().lower() == "respond-async":
                return True
    try:
        config = api_context.dependencies.config
    except AttributeError:
        return False
    try:
        return bool(config.get_bool("MODELS.ROUTING.HTTP_ASYNC_ACCEPT_DEFAULT"))
    except AttributeError:
        return False
