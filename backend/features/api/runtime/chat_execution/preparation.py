"""SoAI - OpenAI prepared chat execution construction [backend/features/api/runtime/chat_execution/preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from inspect import isawaitable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from pydantic import BaseModel
from starlette.responses import Response

from core.events.types_models_requests import InferenceRequestReceived
from core.logging.trace import get_logger
from core.openai.inference_normalization import normalize_openai_inference_payload
from core.openai.request_field_validation import raise_unsupported_field
from core.openai.request_options import extract_openai_bool_flag
from core.openai.request_pipeline import (
    is_openai_chat_completions_path,
)
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.system_api.request_paths import get_scope_path
from core.timing.epoch import epoch_ms
from core.users.user_id import coerce_user_id
from features.api.runtime.chat_execution.contracts import (
    PreparedChatExecution,
    PreparedChatExecutionStorage,
)
from features.api.runtime.chat_execution.quota_application import (
    apply_token_quota_reservation_to_request,
)
from features.api.runtime.chat_execution.request_resolution import (
    resolve_task_owner,
    should_use_async_accept,
)
from features.api.runtime.chat_execution.storage_settings import (
    resolve_chat_completion_storage_settings,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.inference_request_model_resolution import (
    resolve_effective_inference_model_resolution,
)
from features.api.runtime.openai_error_conversion import (
    build_openai_http_exception_response,
)
from features.api.runtime.openai_request_state import (
    apply_stored_chat_completion_model_override,
    record_stored_chat_completion_request_json,
)
from features.api.runtime.openai_request_validation import (
    extract_openai_store_flag_or_response,
    extract_unknown_extra_fields,
    validate_openai_stream_options_or_response,
)
from features.api.runtime.tool_request.preparation import prepare_mcp_tools_for_request

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict

__all__ = ("prepare_openai_chat_execution",)

LOGGER_NAME = "SoAI.features.api.preparation"


async def prepare_openai_chat_execution(
    *,
    request: Request,
    api_context: ApiContext,
    request_event_class: type[InferenceRequestReceived],
    payload: BaseModel,
    base_capabilities: tuple[str, ...],
    request_json_preprocessor: Callable[[ApiContext, JSONDict], Awaitable[None] | None] | None,
    prompt_count: PromptOccupancy | None = None,
) -> PreparedChatExecution | Response:
    context = request.state.context
    request_source = resolve_request_source_for_request(request)
    request_json = await _prepare_openai_request_json(
        request=request,
        api_context=api_context,
        payload=payload,
        request_json_preprocessor=request_json_preprocessor,
    )
    if isinstance(request_json, Response):
        return request_json
    prepared_tool_request = None
    prepared_agent_request = None
    if request_event_class is InferenceRequestReceived and isinstance(
        request_json.get("messages"),
        list,
    ):
        now_ms = epoch_ms()
        prepared_tool_request = await prepare_mcp_tools_for_request(
            request=request,
            api_context=api_context,
            request_json=request_json,
            context=context,
            request_source=request_source,
            assistant_at_ms=now_ms,
            assistant_turn_at_ms=now_ms,
            model_variant_index=0,
            force_tool_approval_required=False,
        )
        request_json = prepared_tool_request.request_json
        prepared_agent_request = prepared_tool_request.prepared_agent_request
        if prepared_tool_request.tool_context is None or prepared_agent_request is None:
            prepared_tool_request = None
    model_resolution = resolve_effective_inference_model_resolution(
        request_json=request_json,
        request_context=context,
        prepared_agent_request=prepared_agent_request,
        apply_to_request_json=True,
    )
    request_json = model_resolution.request_json
    if model_resolution.model_overridden and model_resolution.override_model_id is not None:
        apply_stored_chat_completion_model_override(
            request,
            override_model_id=model_resolution.override_model_id,
        )
    key_id, reservation, quota_error_response, prompt_tokens = (
        await apply_token_quota_reservation_to_request(
            request,
            api_context,
            request_json,
            prompt_count=prompt_count,
        )
    )
    if quota_error_response is not None:
        return quota_error_response
    normalized_for_capabilities = normalize_openai_inference_payload(
        request_json,
        logger=get_logger(LOGGER_NAME),
        trace_id=context.trace_id,
        base_capabilities=base_capabilities,
        filter_request_fields=True,
    )
    store_chat_completion, stored_request_json = resolve_chat_completion_storage_settings(
        request=request,
        request_json=request_json,
    )
    if store_chat_completion:
        async_accept_requested = False
    else:
        async_accept_requested = should_use_async_accept(request, api_context)
    owner_type, owner_id = resolve_task_owner(context, request_json)
    return PreparedChatExecution(
        request_context=context,
        request_json=request_json,
        inference_payload=normalized_for_capabilities.payload,
        request_event_class=request_event_class,
        request_source=request_source,
        effective_model_id=model_resolution.effective_model_id,
        required_capabilities=normalized_for_capabilities.required_capabilities,
        required_modalities=normalized_for_capabilities.required_modalities,
        tool_context=(
            prepared_tool_request.tool_context if prepared_tool_request is not None else None
        ),
        prepared_agent_request=prepared_agent_request,
        api_key_id=key_id,
        quota_reservation=reservation,
        prompt_tokens=prompt_tokens,
        user_id=coerce_user_id(context.user_id),
        owner_type=owner_type,
        owner_id=owner_id,
        cancellation_id=context.cancellation_id.strip(),
        is_streaming=extract_openai_bool_flag(
            request_json,
            key="stream",
            default=False,
            trace_id=context.trace_id,
        ),
        async_accept_requested=async_accept_requested,
        storage=PreparedChatExecutionStorage(
            store_chat_completion=store_chat_completion,
            stored_request_json=stored_request_json,
        ),
    )


async def _prepare_openai_request_json(
    *,
    request: Request,
    api_context: ApiContext,
    payload: BaseModel,
    request_json_preprocessor: Callable[[ApiContext, JSONDict], Awaitable[None] | None] | None,
) -> JSONDict | Response:
    context = request.state.context
    unknown_extra_fields = extract_unknown_extra_fields(payload)
    if unknown_extra_fields:
        raise_unsupported_field(unknown_extra_fields[0], trace_id=context.trace_id)
    request_json = payload.model_dump(exclude_none=True, exclude_unset=True, by_alias=True)
    is_chat_completions = is_openai_chat_completions_path(get_scope_path(request.scope))
    request_json = normalize_openai_inference_payload(
        request_json,
        logger=get_logger(LOGGER_NAME),
        trace_id=context.trace_id,
        filter_request_fields=False,
    ).payload
    if request_json_preprocessor is not None:
        preprocessor_result = request_json_preprocessor(api_context, request_json)
        if isawaitable(preprocessor_result):
            await preprocessor_result
    stream_options_error = validate_openai_stream_options_or_response(
        request_json,
        trace_id=context.trace_id,
        allow_include_usage=True,
    )
    if stream_options_error is not None:
        return stream_options_error
    if is_chat_completions and "store" in request_json:
        store_requested, store_error = extract_openai_store_flag_or_response(
            request_json,
            default=False,
            trace_id=context.trace_id,
            invalid_message="Invalid store value.",
        )
        if store_error is not None:
            return store_error
        request_json["store"] = bool(store_requested)
    else:
        store_requested = False
    if store_requested and request.state.auth_method != "openai_api_key":
        return build_openai_http_exception_response(
            HTTPException(status_code=401, detail="You are not authenticated."),
            trace_id=context.trace_id,
        )
    if store_requested:
        record_stored_chat_completion_request_json(request, request_json)
    return request_json
