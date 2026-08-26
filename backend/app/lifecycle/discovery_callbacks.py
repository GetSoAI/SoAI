"""SoAI - Discovery server cancellation callback construction [backend/app/lifecycle/discovery_callbacks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING

from app.lifecycle.discovery_http_server import DiscoveryHTTPServer
from app.lifecycle.discovery_runtime import (
    DiscoveryServerThreadState,
    shutdown_discovery_server,
)
from core.concurrency.cancellation import make_task_cancel_callback
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = (
    "build_discovery_release_token_callback",
    "build_discovery_shutdown_server_callback",
)

OPERATION_DISCOVERY_SCHEDULE_SERVER_SHUTDOWN = (
    "app.lifecycle.discovery_callbacks.schedule_server_shutdown"
)
OPERATION_DISCOVERY_SCHEDULE_TOKEN_RELEASE = (
    "app.lifecycle.discovery_callbacks.schedule_token_release"
)

if TYPE_CHECKING:
    type ReleaseTokenCoroutineFactory = Callable[
        [CancellationTokenProtocol, str],
        Coroutine[None, None, None],
    ]

DISCOVERY_SHUTDOWN_SCHEDULE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def build_discovery_shutdown_server_callback(
    *,
    server: DiscoveryHTTPServer,
    server_thread_state: DiscoveryServerThreadState,
    port_number: int,
    task_holder: dict[str, asyncio.Task[None] | None],
    cancellation_id: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    event_loop: asyncio.AbstractEventLoop,
    logger: LoggerProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> Callable[[str], None]:
    def _shutdown_server(reason: str) -> None:
        try:
            _ = spawn_tracked_task(
                shutdown_discovery_server(server, server_thread_state),
                loop=event_loop,
                name=f"discovery-server-shutdown-{port_number}",
                logger=logger,
                cancellation_binder=cancellation_binder,
                cancellation_id=f"{cancellation_id}::shutdown",
                owner="port_discovery_server_shutdown",
                finalizer_tracker=finalizer_tracker,
            )
        except RuntimeError as exception:
            if event_loop.is_closed():
                logger.debug(
                    "Discovery shutdown task was not scheduled because the event loop closed."
                )
            else:
                log_exception(
                    logger,
                    exception,
                    message="Failed to schedule discovery server shutdown.",
                    operation=OPERATION_DISCOVERY_SCHEDULE_SERVER_SHUTDOWN,
                )
        except DISCOVERY_SHUTDOWN_SCHEDULE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to schedule discovery server shutdown.",
                operation=OPERATION_DISCOVERY_SCHEDULE_SERVER_SHUTDOWN,
            )
        active_task = task_holder["task"]
        if active_task is not None:
            make_task_cancel_callback(
                event_loop,
                active_task,
                cancellation_id,
                "port_discovery_server",
            )(reason)

    return _shutdown_server


def build_discovery_release_token_callback(
    *,
    event_loop: asyncio.AbstractEventLoop,
    token: CancellationTokenProtocol,
    cancellation_id: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    release_token: ReleaseTokenCoroutineFactory,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: LoggerProtocol,
) -> Callable[[asyncio.Task[None]], None]:
    def _release_token(_completed: asyncio.Task[None]) -> None:
        if event_loop.is_closed():
            return
        try:
            cleanup_task = spawn_tracked_task(
                release_token(token, cancellation_id),
                loop=event_loop,
                name=f"discovery-release-token:{cancellation_id}",
                cancellation_binder=cancellation_binder,
                cancellation_id=f"{cancellation_id}::release",
                owner="port_discovery_token_release",
                finalizer_tracker=finalizer_tracker,
            )
        except RuntimeError as exception:
            if event_loop.is_closed():
                logger.debug(
                    "Discovery token release was not scheduled because the event loop closed."
                )
            else:
                log_exception(
                    logger,
                    exception,
                    message="Failed to schedule discovery token release.",
                    operation=OPERATION_DISCOVERY_SCHEDULE_TOKEN_RELEASE,
                )
            return
        except DISCOVERY_SHUTDOWN_SCHEDULE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to schedule discovery token release.",
                operation=OPERATION_DISCOVERY_SCHEDULE_TOKEN_RELEASE,
            )
            return
        finalizer_tracker.track_finalizer(cleanup_task)

    return _release_token
