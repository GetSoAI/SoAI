"""SoAI - Restricted setup-status WebSocket lifecycle [backend/features/api/routes/system/events/websocket_setup_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import WebSocket

from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.task_groups import cancel_and_await
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_webui import UserCreatedEvent
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.users.bootstrap_state import BootstrapState
from features.api.routes.system.events.websocket_transport_lifecycle import (
    WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS,
    is_websocket_close_state_error,
    should_close_websocket_application_state,
)
from features.api.runtime.context import ApiContext

__all__ = ("run_setup_status_channel",)

LOGGER_NAME = "SoAI.features.api.websocket_setup_status"
OPERATION_SETUP_STATUS_CHANNEL = "api_system.websocket.setup_status"


async def run_setup_status_channel(websocket: WebSocket, api_context: ApiContext) -> None:
    dependencies = api_context.dependencies
    admission = dependencies.setup_status_connection_semaphore
    if admission.locked():
        await websocket.close(code=1013, reason="Setup status connection capacity is busy")
        return
    await admission.acquire()
    changed = asyncio.Event()
    changed.set()
    event_bus = dependencies.event_bus
    close_code = 1000
    close_reason = "Setup status closed"
    tasks: list[asyncio.Task[None]] = []

    async def request_snapshot(event: Event) -> None:
        if isinstance(event, UserCreatedEvent) and event.user_id > 0:
            changed.set()

    async def send_snapshots() -> None:
        while True:
            await changed.wait()
            changed.clear()
            state = await dependencies.webui_manager.get_bootstrap_state()
            if state == BootstrapState.INTEGRITY_ERROR:
                raise StateError("Setup status requires consistent durable bootstrap state.")
            async with asyncio.timeout(CONTROL_TIMEOUT_SEC):
                await websocket.send_json(
                    {
                        "type": "setup_status",
                        "data": {
                            "setup_needed": state == BootstrapState.UNINITIALIZED,
                            "has_users": state == BootstrapState.COMPLETE,
                        },
                    }
                )
            if state == BootstrapState.COMPLETE:
                return

    async def receive_disconnect() -> None:
        nonlocal close_code, close_reason
        message = await websocket.receive()
        if message["type"] != "websocket.disconnect":
            close_code, close_reason = 4003, "Setup status channel is read-only"

    async def observe_shutdown() -> None:
        nonlocal close_code, close_reason
        await dependencies.shutdown_event.wait()
        close_code, close_reason = 1001, "Setup status service is stopping"

    subscribed = False
    try:
        event_bus.subscribe(UserCreatedEvent, request_snapshot)
        subscribed = True
        async with asyncio.timeout(CONTROL_TIMEOUT_SEC):
            await websocket.accept()
        cancellation_id = create_system_id(
            subsystem="setup_status", owner="connection", include_random_suffix=True
        )
        for coroutine_factory, name in (
            (send_snapshots, "setup-status-sender"),
            (receive_disconnect, "setup-status-receiver"),
            (observe_shutdown, "setup-status-shutdown"),
        ):
            tasks.append(
                spawn_tracked_task(
                    coroutine_factory(),
                    name=name,
                    logger=get_logger(LOGGER_NAME),
                    cancellation_binder=dependencies.task_cancellation_binder,
                    finalizer_tracker=dependencies.task_finalizer_tracker,
                    cancellation_id=cancellation_id,
                    owner="setup_status",
                    owner_observes_result=True,
                )
            )
        completed = await wait_for_first_completed_tasks(set(tasks), cancel_pending=False)
        for task in completed:
            task.result()
    except asyncio.CancelledError:
        close_code, close_reason = 1001, "Setup status connection cancelled"
        raise
    except WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS:
        close_code, close_reason = 1001, "Setup status client disconnected"
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        close_code, close_reason = 1011, "Setup status is unavailable"
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Restricted setup status channel is unavailable.",
            operation=OPERATION_SETUP_STATUS_CHANNEL,
            level="warning" if isinstance(exception, RECOVERABLE_EXCEPTIONS) else "error",
        )
    finally:
        if subscribed:
            event_bus.unsubscribe(UserCreatedEvent, request_snapshot)
        try:
            await cancel_and_await(tasks, task_label="setup-status connection")
            for task in tasks:
                await wait_for_task_completion(task, retain_resources_until_complete=True)
        finally:
            try:
                if should_close_websocket_application_state(websocket):
                    async with asyncio.timeout(CONTROL_TIMEOUT_SEC):
                        await websocket.close(code=close_code, reason=close_reason)
            except WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS:
                get_logger(LOGGER_NAME).debug(
                    "Setup status transport disconnected before final close."
                )
            except RuntimeError as exception:
                if not is_websocket_close_state_error(exception):
                    raise
            finally:
                admission.release()
