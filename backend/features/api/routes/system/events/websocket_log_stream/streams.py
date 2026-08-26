"""SoAI - WebSocket log streaming with backpressure handling [backend/features/api/routes/system/events/websocket_log_stream/streams.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_ops import QueueDropTracker
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggingManagerProtocol, TraceLogger
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.progress import StreamBackpressureController
from core.types.json_value import filter_json_dict_list
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_cancellation_ids import (
    resolve_connection_cancellation_id_or_create,
)
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_log_stream.delivery import (
    enqueue_log_batch,
    record_log_drop,
)
from features.api.routes.system.events.websocket_log_stream.events import (
    build_log_batch_payload,
    build_log_stream_closed_payload,
    build_log_stream_reconfigured_payload,
    build_log_stream_subscribed_payload,
)
from features.api.routes.system.events.websocket_log_stream.stop import stop_log_stream
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.log_source_resolution import resolve_log_source_name
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "start_log_stream",
    "stop_log_stream",
)

LOGGER_NAME = "SoAI.features.api.streams"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_LOG_STREAM_FORWARD = (
    "api_system.websocket.system_events.log_stream.forward"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_LOG_STREAM_SUBSCRIPTION = (
    "api_system.websocket.system_events.log_stream.subscription"
)


_LOG_STREAM_DROP_WARNING_INTERVAL_SECONDS: float = 30.0


async def _forward_log_stream(
    *,
    logger: TraceLogger,
    connection: WebsocketConnection,
    log_manager: LoggingManagerProtocol,
    normalized: str,
    resolved_source_name: str,
    history_limit: int | None,
    shutdown_event: asyncio.Event,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    log_backpressure_controller = StreamBackpressureController()
    drop_tracker = QueueDropTracker(_LOG_STREAM_DROP_WARNING_INTERVAL_SECONDS)
    timeout = connection.api_context.dependencies.config.get_float(
        "SERVER.HTTP.LOG_STREAM.TIMEOUT_SEC",
    )
    batch_size = connection.api_context.dependencies.config.get_int(
        "SERVER.HTTP.LOG_STREAM.BATCH_SIZE",
    )
    idle_ping = (
        connection.api_context.dependencies.config.get_int("SERVER.HTTP.LOG_STREAM.INTERVAL_MS")
        / 1000.0
    )
    try:
        async for event in log_manager.stream_log_batches(
            resolved_source_name,
            batch_size=batch_size,
            timeout=timeout,
            shutdown_event=shutdown_event,
            idle_ping_interval=idle_ping,
            min_batch_interval=idle_ping,
            history_limit=history_limit,
        ):
            if event.get("type") == "batch":
                entries_value = event.get("entries", [])
                entries = filter_json_dict_list(entries_value)
                batch_mode_value = event.get("mode", "live")
                batch_mode = batch_mode_value if isinstance(batch_mode_value, str) else "live"
                queue_depth = connection.queue.qsize()
                queue_max = connection.queue.maxsize
                backoff_sec, max_entries = log_backpressure_controller.compute_parameters(
                    queue_depth,
                    queue_max,
                )
                if batch_mode != "history" and entries and max_entries < len(entries):
                    dropped = len(entries) - max_entries
                    entries = entries[-max_entries:]
                    record_log_drop(
                        logger,
                        connection,
                        dropped,
                        queue_depth,
                        queue_max,
                        drop_tracker=drop_tracker,
                    )
                _ = await enqueue_log_batch(
                    logger,
                    connection,
                    build_log_batch_payload(resolved_source_name, batch_mode, entries),
                    len(entries),
                    shutdown_event,
                    drop_tracker=drop_tracker,
                )
                if backoff_sec > 0:
                    await asyncio.sleep(backoff_sec)
            elif event.get("type") == "reconfigured":
                enqueue_event_or_warn(
                    enqueue_warning_tracker,
                    connection.queue,
                    build_log_stream_reconfigured_payload(normalized),
                    "WebSocket log stream reconfigured",
                )
                return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="WebSocket log stream error",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_LOG_STREAM_FORWARD,
            details={"source_name": normalized},
        )
    finally:
        is_replacement = resolved_source_name in connection.log_stream_replacements
        current_log_entry = connection.log_streams.get(resolved_source_name)
        if current_log_entry is None or current_log_entry is asyncio.current_task():
            connection.log_streams.pop(resolved_source_name, None)
        if not is_replacement:
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_log_stream_closed_payload(resolved_source_name),
                "WebSocket log stream closed",
            )


async def start_log_stream(
    source_name: str,
    *,
    connection: WebsocketConnection,
    shutdown_event: asyncio.Event,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    history_limit: int | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    normalized = (source_name or "").strip()
    if not normalized:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            "source_name is required to subscribe.",
            code="invalid_request_error",
        )
        return
    if AccessAction.LOG_ACCESS not in connection.granted_actions:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            "Insufficient permissions to subscribe to log streams.",
            code="forbidden_error",
            details={"source_name": normalized},
        )
        return
    resolved_source_name = resolve_log_source_name(connection.api_context.dependencies, normalized)
    if resolved_source_name in connection.log_streams:
        await stop_log_stream(
            resolved_source_name,
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            emit_event=False,
            suppress_closed_event=True,
        )
        connection.log_streams.pop(resolved_source_name, None)
    log_manager = connection.api_context.dependencies.log_manager
    if log_manager is None:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            "Log streaming is unavailable.",
            code="service_unavailable",
            details={"source_name": normalized},
        )
        return
    try:
        await asyncio.to_thread(log_manager.get_recent_logs, resolved_source_name, 1)
    except ValidationError as exception:
        not_found_error = NotFoundError(
            "Log source not found.",
            operation="api_system.websocket.system_events.log_stream.subscription",
            details={"source_name": normalized},
            cause=exception,
        )
        log_exception(
            logger,
            not_found_error,
            message="Log source not found during stream subscription",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_LOG_STREAM_SUBSCRIPTION,
            details={"source_name": resolved_source_name},
            level="warning",
        )
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            not_found_error.message,
            code="not_found_error",
            details={"source_name": normalized},
        )
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Log stream subscription preflight failed",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_LOG_STREAM_SUBSCRIPTION,
            details={"source_name": resolved_source_name},
            level="warning",
        )
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            "Log streaming is unavailable.",
            code="service_unavailable",
            details={"source_name": resolved_source_name},
        )
        return

    connection.log_streams[resolved_source_name] = None
    cancellation_id = resolve_connection_cancellation_id_or_create(
        connection,
        subsystem="ws_log_stream",
        trace_id=trace_id,
        owner=resolved_source_name,
    )
    forward_task = spawn_tracked_task(
        _forward_log_stream(
            logger=logger,
            connection=connection,
            log_manager=log_manager,
            normalized=normalized,
            resolved_source_name=resolved_source_name,
            history_limit=history_limit,
            shutdown_event=shutdown_event,
            enqueue_warning_tracker=enqueue_warning_tracker,
        ),
        name=f"ws-log-stream-{resolved_source_name}",
        logger=logger,
        cancellation_binder=connection.api_context.dependencies.task_cancellation_binder,
        cancellation_id=cancellation_id,
        owner="ws_log_stream",
        finalizer_tracker=connection.api_context.dependencies.task_finalizer_tracker,
    )
    connection.log_streams[resolved_source_name] = forward_task
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_log_stream_subscribed_payload(resolved_source_name),
        "WebSocket log stream subscribed",
    )
