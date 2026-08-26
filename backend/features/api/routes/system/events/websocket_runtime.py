"""SoAI - WebSocket event subscription streaming and PTY handling [backend/features/api/routes/system/events/websocket_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_ids import normalize_cancellation_id
from features.api.routes.system.events.conversation_presence import (
    remove_conversation_presence,
)
from features.api.routes.system.events.websocket_cleanup import (
    cleanup_websocket_connection,
)
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)
from features.api.routes.system.events.websocket_event_subscriptions import (
    register_websocket_event_subscriptions,
)
from features.api.routes.system.events.websocket_receiver import run_websocket_receiver
from features.api.routes.system.events.websocket_sender import run_websocket_sender
from features.api.routes.system.events.websocket_session_validation import (
    validate_websocket_session,
)
from features.api.routes.system.events.websocket_task_spawning import (
    create_managed_task,
)

__all__ = ("run_websocket_events",)

LOGGER_NAME = "SoAI.features.api.websocket_runtime"


async def run_websocket_events(
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    logger = get_logger(LOGGER_NAME)
    api_context = runtime_context.api_context
    event_bus = api_context.dependencies.event_bus
    connection_shutdown_event = asyncio.Event()
    if runtime_context.shutdown_event.is_set():
        connection_shutdown_event.set()
    try:
        context = runtime_context.request_adapter.state.context
    except AttributeError:
        context = None
    cancellation_id_value = context.cancellation_id if context is not None else None
    cancellation_id = normalize_cancellation_id(cancellation_id_value)
    if not cancellation_id:
        cancellation_id = create_system_id(
            subsystem="ws_system_events",
            owner=str(runtime_context.trace_id or "unknown"),
            include_random_suffix=True,
        )

    async def bridge_shutdown() -> None:
        await runtime_context.shutdown_event.wait()
        connection_shutdown_event.set()

    bridge_task = create_managed_task(
        bridge_shutdown(),
        name="ws-events-shutdown-bridge",
        logger=logger,
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=cancellation_id,
        owner="ws_events_shutdown_bridge",
    )
    event_handler = register_websocket_event_subscriptions(
        event_bus=event_bus,
        api_context=api_context,
        connection=runtime_context.connection,
        enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
        shutdown_event=connection_shutdown_event,
    )
    runtime_context.connection.event_handler = event_handler

    sender_task: asyncio.Task[None] | None = None
    receiver_task: asyncio.Task[None] | None = None
    try:
        session_valid = await validate_websocket_session(
            runtime_context.connection,
            force=True,
        )
        if not session_valid or connection_shutdown_event.is_set():
            return
        sender_task = create_managed_task(
            run_websocket_sender(
                websocket=runtime_context.websocket,
                connection=runtime_context.connection,
                shutdown_event=connection_shutdown_event,
            ),
            name="ws-events-sender",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
            cancellation_id=cancellation_id,
            owner="ws_events_sender",
        )
        receiver_task = create_managed_task(
            run_websocket_receiver(
                runtime_context=runtime_context.with_shutdown_event(connection_shutdown_event),
            ),
            name="ws-events-receiver",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
            cancellation_id=cancellation_id,
            owner="ws_events_receiver",
        )
        done_tasks = await wait_for_first_completed_tasks(
            {sender_task, receiver_task},
        )
        completion_results = await asyncio.gather(*done_tasks, return_exceptions=True)
        for completion_result in completion_results:
            if isinstance(completion_result, asyncio.CancelledError):
                raise completion_result
            if isinstance(completion_result, BaseException):
                raise completion_result
    finally:
        connection_shutdown_event.set()
        remove_conversation_presence(runtime_context)
        await cancel_and_await(
            [bridge_task],
            logger=logger,
            task_label="websocket bridge task",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
        await cancel_and_await(
            [sender_task],
            logger=logger,
            task_label="websocket sender task",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
        await cancel_and_await(
            [receiver_task],
            logger=logger,
            task_label="websocket receiver task",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
        await cleanup_websocket_connection(
            event_bus=event_bus,
            connection=runtime_context.connection,
            api_context=api_context,
            websocket=runtime_context.websocket,
            event_handler=event_handler,
            trace_id=runtime_context.trace_id,
        )
