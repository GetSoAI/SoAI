"""SoAI - WebSocket message handlers for model test streaming [backend/features/api/routes/system/events/websocket_model_test_stream/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.activity_payloads import build_activity_payload
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.timing.monotonic import monotonic_ms
from core.types.json_value import coerce_json_dict
from core.users.user_id import coerce_user_id
from features.api.routes.system.events.websocket_model_test_stream.failure_events import (
    publish_model_test_stream_error,
)
from features.api.routes.system.events.websocket_model_test_stream.request_preparation import (
    build_model_test_stream_request_json,
    prepare_model_test_stream_request,
    publish_model_test_start_error,
)
from features.api.routes.system.events.websocket_model_test_stream.runner import (
    run_ws_model_test_stream,
    schedule_ws_model_test_stream_cancel,
)
from features.api.routes.system.events.websocket_model_test_stream.state import (
    ModelTestStreamRuntime,
    publish_model_test_stream_event,
)
from features.api.routes.system.events.websocket_run_payloads import (
    require_run_id,
    resolve_run_id,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_model_test_stream_cancel",
    "handle_model_test_stream_start",
)

LOGGER_NAME = "SoAI.features.api.handlers"
OPERATION_MODEL_TEST_STREAM_START_VALIDATE = "model_test_stream.start.validate"
OPERATION_MODEL_TEST_STREAM_START_SPAWN = "model_test_stream.start.spawn"


async def handle_model_test_stream_start(
    data: JSONDict,
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    stream_dependencies: StreamDependencies,
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    context = request.state.context
    try:
        user_id_value = context.user_id
    except AttributeError:
        user_id_value = None
    user_id = coerce_user_id(user_id_value)
    run_id_hint = resolve_run_id(data) or ""
    if AccessAction.AUTH_COOKIE not in connection.granted_actions:
        await publish_model_test_start_error(
            api_context=api_context,
            run_id=run_id_hint,
            user_id=int(user_id),
            message="Insufficient permissions.",
            code="forbidden_error",
        )
        return
    try:
        run_id = require_run_id(data)
        openai_request_raw = data.get("openai_request")
        openai_request = coerce_json_dict(openai_request_raw)
        if openai_request is None:
            raise ValidationError("openai_request must be a JSON object.")
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid WebSocket model test stream start payload (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_MODEL_TEST_STREAM_START_VALIDATE,
            level="debug",
        )
        await publish_model_test_start_error(
            api_context=api_context,
            run_id=run_id_hint,
            user_id=int(user_id),
            message=str(exception),
            code="invalid_request_error",
        )
        return

    streams = connection.model_test_streams
    if run_id in streams:
        await publish_model_test_start_error(
            api_context=api_context,
            run_id=run_id,
            user_id=int(user_id),
            message="A model test stream is already active for this run_id.",
            code="conflict_error",
        )
        return

    try:
        request_json = build_model_test_stream_request_json(
            openai_request=openai_request,
            logger=logger,
            trace_id=trace_id,
        )
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid WebSocket model test stream request (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_MODEL_TEST_STREAM_START_VALIDATE,
            level="debug",
        )
        await publish_model_test_start_error(
            api_context=api_context,
            run_id=run_id,
            user_id=int(user_id),
            message=str(exception),
            code="invalid_request_error",
        )
        return
    prepared_request = await prepare_model_test_stream_request(
        request_json=request_json,
        run_id=run_id,
        user_id=int(user_id),
        trace_id=trace_id,
        logger=logger,
        api_context=api_context,
    )
    if prepared_request is None:
        return

    started_at_ms = monotonic_ms()
    runtime = ModelTestStreamRuntime(
        run_id=run_id,
        user_id=user_id,
        started_at_ms=started_at_ms,
        detach_event=asyncio.Event(),
    )
    streams[run_id] = runtime

    await publish_model_test_stream_event(
        api_context.dependencies.event_bus,
        runtime,
        event_type="loading",
        payload={
            "loading": build_activity_payload(
                status="running",
                started_at_ms=int(started_at_ms),
                duration_ms=0,
                reason=None,
                error_type=None,
            ),
        },
    )

    async def run_and_cleanup() -> None:
        try:
            await run_ws_model_test_stream(
                request=request,
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                runtime=runtime,
                request_json=prepared_request.request_json,
            )
        finally:
            existing = streams.get(run_id)
            if existing is runtime:
                del streams[run_id]

    try:
        task = create_ephemeral_task(run_and_cleanup(), name=f"ws-model-test-stream-{run_id}")
    except RECOVERABLE_EXCEPTIONS as exception:
        existing = streams.get(run_id)
        if existing is runtime:
            del streams[run_id]
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MODEL_TEST_STREAM_START_SPAWN,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to start WebSocket model test background task.",
            trace_id=trace_id,
            operation=OPERATION_MODEL_TEST_STREAM_START_SPAWN,
            level="error",
            details={"run_id": run_id},
        )
        await publish_model_test_stream_error(
            event_bus=api_context.dependencies.event_bus,
            runtime=runtime,
            exception=coerced,
        )
        return
    api_context.dependencies.application_control.track_background_task(task)


async def handle_model_test_stream_cancel(
    data: JSONDict,
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
) -> None:
    if AccessAction.AUTH_COOKIE not in connection.granted_actions:
        return
    run_id = resolve_run_id(data)
    if run_id is None:
        return
    streams = connection.model_test_streams
    runtime = streams.get(run_id)
    if runtime is None:
        return
    reason_value = data.get("reason")
    reason = (
        reason_value.strip()
        if isinstance(reason_value, str) and reason_value.strip()
        else "User requested cancellation via WebUI."
    )
    schedule_ws_model_test_stream_cancel(
        api_context=api_context,
        request=request,
        runtime=runtime,
        reason=reason,
    )
    if runtime.detach_event is not None:
        runtime.detach_event.set()
