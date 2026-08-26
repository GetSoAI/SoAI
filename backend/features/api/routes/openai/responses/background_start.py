"""SoAI - OpenAI Responses background request startup [backend/features/api/routes/openai/responses/background_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import StateError
from core.openai.responses_events import (
    build_response_status_event,
    build_response_status_json,
)
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.tasks.task_cancellation import cancel
from core.timing.epoch import epoch_ms, epoch_seconds
from core.types.json import JSONDict
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.routes.openai.responses.background_monitor_runner import (
    monitor_background_responses_task,
)
from features.api.routes.openai.responses.background_monitor_state import (
    BackgroundResponsesState,
)
from features.api.routes.openai.responses.endpoint_family_streaming import (
    create_response_events_stream,
)
from features.api.routes.openai.responses.passthrough_task_setup import (
    ResponsesTaskSetupResult,
)
from features.api.routes.openai.storage_owner import resolve_responses_storage_owner
from features.api.runtime.context import ApiContext
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import (
    apply_operation_id_header,
    apply_task_id_header,
    build_task_operation_headers,
)

__all__ = ("start_background_response_request",)


async def start_background_response_request(
    *,
    request: Request,
    api_context: ApiContext,
    task_setup: ResponsesTaskSetupResult,
    model: str,
    effective_input_items: tuple[JSONDict, ...],
    stream_enabled: bool,
) -> Response:
    context = request.state.context
    response_id = create_prefixed_hex_id("resp")
    created_at = int(epoch_seconds())
    now_ms = int(epoch_ms())
    response_json = build_response_status_json(
        response_id=response_id,
        status="queued",
        model=model,
        created_at=created_at,
    )
    requesting_api_key_id, requesting_user_id = resolve_responses_storage_owner(request)
    persisted = await api_context.dependencies.database_openai_responses.upsert_response_artifacts(
        response_id=response_id,
        task_id=task_setup.task.task_id,
        user_id=requesting_user_id,
        api_key_id=requesting_api_key_id,
        model=model,
        created_at_seconds=created_at,
        status="queued",
        store=True,
        is_background=True,
        stream_enabled=stream_enabled,
        response_json=dict(response_json),
        input_items=effective_input_items,
        input_items_created_at_ms=now_ms,
        event_payloads=(
            {
                **build_response_status_event(
                    response_id=response_id,
                    status="queued",
                    model=model,
                    created_at=created_at,
                ),
                "sequence_number": 0,
            },
        ),
        event_sequence_start=0,
        reset_events=True,
        create_if_missing=True,
        event_created_at_ms=now_ms,
    )
    if not persisted:
        raise StateError("Initial background Response persistence was rejected.")
    monitor_state = BackgroundResponsesState(
        response_id=response_id,
        task_id=task_setup.task.task_id,
        user_id=requesting_user_id,
        api_key_id=requesting_api_key_id,
        model=model,
        created_at=created_at,
        event_sequence=1,
        stream_enabled=stream_enabled,
    )
    scheduled_monitor = api_context.dependencies.application_control.schedule_background_task(
        monitor_background_responses_task(
            api_context=api_context,
            context=context,
            reply_queue=task_setup.reply_channel,
            state=monitor_state,
        ),
        name=f"openai.responses.background.{response_id}",
    )
    if scheduled_monitor is None:
        await cancel(
            api_context.dependencies.task_registry,
            task_setup.task.task_id,
            reason="Background response monitor could not be scheduled.",
            context=context,
        )
        response_deleted = await api_context.dependencies.database_openai_responses.delete_response(
            response_id=response_id,
            user_id=requesting_user_id,
            api_key_id=requesting_api_key_id,
        )
        if not response_deleted:
            raise StateError("Unmonitored background Response could not be rolled back.")
        return build_openai_error_json_response_for_status(
            status_code=503,
            message="Background response monitoring is unavailable.",
            soai_code="service_unavailable",
            param=None,
            trace_id=context.trace_id,
            headers=None,
        )
    if stream_enabled:
        return create_response_events_stream(
            request=request,
            api_context=api_context,
            response_id=response_id,
            starting_after=-1,
            limit=1000,
            user_id=requesting_user_id,
            api_key_id=requesting_api_key_id,
            additional_headers=build_task_operation_headers(
                task_id=task_setup.task.task_id,
                operation_id=None,
            ),
        )
    response = create_json_body_response(content=response_json)
    apply_task_id_header(response, task_setup.task.task_id)
    apply_operation_id_header(response, context.trace_id)
    return response
