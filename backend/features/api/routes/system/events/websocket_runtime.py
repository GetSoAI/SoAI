"""SoAI - WebSocket event subscription streaming and PTY handling [backend/features/api/routes/system/events/websocket_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging

from core.concurrency.cancellation_cleanup import current_task_has_pending_cancellation
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from features.api.routes.system.events.conversation_presence import (
    remove_conversation_presence,
)
from features.api.routes.system.events.websocket_cleanup import (
    cleanup_websocket_connection,
    disconnect_websocket_connection,
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
    connection_shutdown_event = runtime_context.connection.authorization.shutdown_event
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

    async def observe_connection_shutdown() -> None:
        await connection_shutdown_event.wait()
        runtime_context.connection.authorization.close()

    bridge_task = create_managed_task(
        bridge_shutdown(),
        name="ws-events-shutdown-bridge",
        logger=logger,
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=cancellation_id,
        owner="ws_events_shutdown_bridge",
        owner_observes_result=True,
    )
    event_handler = register_websocket_event_subscriptions(
        event_bus=event_bus,
        api_context=api_context,
        connection=runtime_context.connection,
        enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
        shutdown_event=connection_shutdown_event,
    )
    runtime_context.connection.event_handler = event_handler

    async def observe_completed_children() -> None:
        children = (bridge_task, shutdown_task, initial_validation_task, sender_task, receiver_task)
        cancelled_child_seen = any(child is not None and child.cancelled() for child in children)
        expected_cancellation = connection_shutdown_event.is_set()
        if cancelled_child_seen and not expected_cancellation:
            expected_cancellation = (
                await api_context.dependencies.cancellation_history.is_cancelled(cancellation_id)
            )
        if current_task_has_pending_cancellation():
            raise asyncio.CancelledError
        for child in children:
            if child is not None and child.done() and not child.cancelled():
                child.result()
        if cancelled_child_seen:
            if expected_cancellation or connection_shutdown_event.is_set():
                connection_shutdown_event.set()
            else:
                raise asyncio.CancelledError

    shutdown_task: asyncio.Task[None] | None = None
    initial_validation_task: asyncio.Task[bool] | None = None
    sender_task: asyncio.Task[None] | None = None
    receiver_task: asyncio.Task[None] | None = None
    try:
        if connection_shutdown_event.is_set():
            return
        shutdown_task = create_managed_task(
            observe_connection_shutdown(),
            name="ws-events-connection-shutdown",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
            cancellation_id=cancellation_id,
            owner="ws_events_connection_shutdown",
            owner_observes_result=True,
        )
        initial_validation_task = spawn_tracked_task(
            validate_websocket_session(runtime_context.connection, force=True),
            name="ws-events-initial-validation",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
            cancellation_id=cancellation_id,
            owner="ws_events_initial_validation",
            owner_observes_result=True,
        )
        completed_tasks = await wait_for_first_completed_tasks(
            {initial_validation_task, shutdown_task, bridge_task},
            cancel_pending=False,
        )
        await observe_completed_children()
        if initial_validation_task in completed_tasks:
            if initial_validation_task.cancelled():
                return
            session_valid = initial_validation_task.result()
        else:
            session_valid = False
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
            owner_observes_result=True,
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
            owner_observes_result=True,
        )
        await wait_for_first_completed_tasks(
            {sender_task, receiver_task, shutdown_task, bridge_task},
            cancel_pending=False,
        )
        await observe_completed_children()
    finally:
        runtime_context.connection.authorization.close()
        remove_conversation_presence(runtime_context)
        await disconnect_websocket_connection(
            event_bus=event_bus,
            connection=runtime_context.connection,
            websocket=runtime_context.websocket,
            event_handler=event_handler,
            trace_id=runtime_context.trace_id,
        )
        await cancel_and_await(
            [bridge_task, shutdown_task, initial_validation_task],
            logger=logger,
            task_label="websocket bridge task",
            log_level=logging.DEBUG,
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            timeout_log_level=logging.DEBUG,
        )
        await cancel_and_await(
            [sender_task],
            logger=logger,
            task_label="websocket sender task",
            log_level=logging.DEBUG,
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            timeout_log_level=logging.DEBUG,
        )
        await cancel_and_await(
            [receiver_task],
            logger=logger,
            task_label="websocket receiver task",
            log_level=logging.DEBUG,
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            timeout_log_level=logging.DEBUG,
        )
        await cleanup_websocket_connection(
            event_bus=event_bus,
            connection=runtime_context.connection,
            api_context=api_context,
            websocket=runtime_context.websocket,
            event_handler=event_handler,
            trace_id=runtime_context.trace_id,
        )
