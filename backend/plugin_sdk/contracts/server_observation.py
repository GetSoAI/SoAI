"""SoAI - Managed server readiness and failure observation [backend/plugin_sdk/contracts/server_observation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass

from core.concurrency.task_groups import cancel_and_await
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    AcceleratorMemoryExhaustedError,
    StateError,
    SystemMemoryExhaustedError,
)
from core.errors.external_service_exception import ExternalServiceError
from core.errors.memory_exhaustion import raise_for_memory_exhaustion
from core.platform.os import is_windows
from core.plugins.protocols_runtime import PluginRuntimeFailureReporterProtocol
from core.timing.constants import ASYNC_POLL_SLICE_SEC, LOCAL_IO_TIMEOUT_SEC, STANDARD_DELAY_SEC
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from plugin_sdk.contracts.process_diagnostics import read_recent_process_log
from plugin_sdk.contracts.process_sessions import ManagedProcessSession, terminate_logged_process

__all__ = ("ServerObservation", "ServerObservationDependencies")

OPERATION_SERVER_OBSERVATION = "plugin_sdk.server_observation"


@dataclass(frozen=True, slots=True)
class ServerObservationDependencies:
    session: ManagedProcessSession
    health_ping: Callable[[], Awaitable[tuple[bool, str]]]
    runtime_reporter: PluginRuntimeFailureReporterProtocol
    logger: logging.Logger
    label: str
    component: str
    log_path: str | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ServerObservationDependencies",
            session=self.session,
            health_ping=self.health_ping,
            runtime_reporter=self.runtime_reporter,
            logger=self.logger,
            label=self.label,
            component=self.component,
        )


class ServerObservation:
    def __init__(self, dependencies: ServerObservationDependencies) -> None:
        self._dependencies = dependencies
        self.failure = asyncio.Event()
        self.ready = False
        self.expected_stop = False
        self.task: asyncio.Task[None] | None = None
        self.failure_exception: BaseException | None = None
        self._health_failures = 0

    @property
    def health_degraded(self) -> bool:
        return self._health_failures > 0

    def start(self) -> None:
        if self.task is not None or self.expected_stop:
            raise StateError("Server observation has already started or stopped.")
        self.task = asyncio.create_task(
            self._observe(), name=f"{self._dependencies.label}.server_observation"
        )
        self.task.add_done_callback(self._finish)

    def _finish(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            exception = task.exception()
            if exception is not None:
                self.failure_exception = exception

    async def _observe_health(self) -> None:
        while not self.ready:
            await asyncio.sleep(ASYNC_POLL_SLICE_SEC)
        while not self.expected_stop:
            healthy, _message = await self._dependencies.health_ping()
            if self.expected_stop:
                return
            if healthy:
                if self.health_degraded:
                    self._dependencies.logger.info("Managed server health recovered")
                self._health_failures = 0
                await asyncio.sleep(STANDARD_DELAY_SEC)
                continue
            self._health_failures += 1
            if self._health_failures == 1:
                self._dependencies.logger.warning(
                    "Managed server health degraded; confirming with bounded probes"
                )
            if self._health_failures >= 3:
                return
            await asyncio.sleep(
                compute_exponential_backoff_seconds(
                    self._health_failures - 1,
                    base_seconds=STANDARD_DELAY_SEC,
                    maximum_seconds=4.0,
                    jitter_ratio=0.1,
                )
            )

    async def _wait_for_exit(self) -> None:
        while self._dependencies.session.process.returncode is None:
            await asyncio.sleep(ASYNC_POLL_SLICE_SEC)

    async def _classify_startup_failure(self) -> None:
        diagnostic = await read_recent_process_log(
            self._dependencies.log_path,
            logger=self._dependencies.logger,
            log_consumer_tasks=self._dependencies.session.log_consumer_tasks,
        )
        try:
            raise_for_memory_exhaustion(diagnostic)
        except (AcceleratorMemoryExhaustedError, SystemMemoryExhaustedError) as exception:
            self.failure_exception = exception

    async def _observe(self) -> None:
        dependencies = self._dependencies
        process_wait = asyncio.create_task(
            self._wait_for_exit(), name=f"{dependencies.label}.process_exit"
        )
        health_wait = asyncio.create_task(
            self._observe_health(), name=f"{dependencies.label}.health_observation"
        )
        terminal_failure = False
        try:
            watched = {process_wait, health_wait, *dependencies.session.log_consumer_tasks}
            completed = await wait_for_first_completed_tasks(watched, cancel_pending=False)
            if self.expected_stop:
                return
            terminal_failure = True
            exit_status = dependencies.session.process.returncode
            failure_code = "process_exited" if exit_status is not None else "output_closed"
            if process_wait in completed and process_wait.exception() is not None:
                self.failure_exception = process_wait.exception()
                failure_code = "observation_failed"
            if health_wait in completed and exit_status is None:
                self.failure_exception = health_wait.exception()
                failure_code = "health_failed"
            for consumer in dependencies.session.log_consumer_tasks:
                if consumer in completed and not consumer.cancelled():
                    exception = consumer.exception()
                    if exception is not None:
                        self.failure_exception = exception
                        failure_code = "output_failed"
            if not self.ready and self.failure_exception is None:
                await self._classify_startup_failure()
            if self.expected_stop:
                return
            self.failure.set()
            dependencies.logger.error(
                "Managed server failure: component=%s code=%s exit_status=%s ready=%s",
                dependencies.component,
                failure_code,
                exit_status,
                self.ready,
            )
            if not isinstance(
                self.failure_exception,
                AcceleratorMemoryExhaustedError | SystemMemoryExhaustedError,
            ):
                await dependencies.runtime_reporter.report_runtime_failure(
                    component=dependencies.component,
                    failure_code=failure_code,
                    exit_status=exit_status,
                )
        except asyncio.CancelledError:
            self.expected_stop = True
            raise
        except Exception as exception:
            unreported_failure = not self.failure.is_set()
            terminal_failure = True
            self.failure_exception = exception
            self.failure.set()
            coerced = coerce_to_soai_error(exception, operation=OPERATION_SERVER_OBSERVATION)
            log_exception(
                dependencies.logger,
                coerced,
                message="Managed server failure handling did not complete",
                operation=OPERATION_SERVER_OBSERVATION,
                details={"label": dependencies.label, "component": dependencies.component},
            )
            if unreported_failure:
                await dependencies.runtime_reporter.report_runtime_failure(
                    component=dependencies.component,
                    failure_code="observation_failed",
                    exit_status=dependencies.session.process.returncode,
                )
            raise
        finally:
            pending_count = await cancel_and_await(
                (process_wait, health_wait),
                logger=dependencies.logger,
                task_label=f"{dependencies.label} observation tasks",
                timeout_sec=LOCAL_IO_TIMEOUT_SEC,
            )
            if terminal_failure:
                terminated = await terminate_logged_process(
                    dependencies.session,
                    logger=dependencies.logger,
                    plugin_label=dependencies.label,
                    shutdown_timeout_sec=0.0,
                    kill_wait_sec=LOCAL_IO_TIMEOUT_SEC,
                    use_process_group=not is_windows(),
                )
                if not terminated:
                    raise ExternalServiceError(
                        "The failed backend could not release all process resources."
                    )
            if pending_count:
                raise ExternalServiceError("The backend observation tasks could not stop.")

    async def wait_until_ready(self, readiness: Coroutine[None, None, None]) -> None:
        dependencies = self._dependencies
        readiness_task = asyncio.create_task(readiness, name=f"{dependencies.label}.readiness")
        failure_wait = asyncio.create_task(
            self.failure.wait(), name=f"{dependencies.label}.startup_failure"
        )
        try:
            completed = await wait_for_first_completed_tasks(
                {readiness_task, failure_wait}, cancel_pending=False
            )
            if readiness_task in completed:
                await readiness_task
        finally:
            pending_count = await cancel_and_await(
                (readiness_task, failure_wait),
                logger=dependencies.logger,
                task_label=f"{dependencies.label} startup tasks",
                timeout_sec=LOCAL_IO_TIMEOUT_SEC,
            )
            if pending_count:
                raise ExternalServiceError("The backend startup tasks could not stop.")
        if self.failure.is_set():
            if self.failure_exception is not None:
                raise self.failure_exception
            error = ExternalServiceError(
                "The backend exited or lost its output connection before readiness. Review server diagnostics and retry."
            )
            error.public_message = error.message
            raise error
        if self.expected_stop:
            raise asyncio.CancelledError
        self.ready = True

    async def stop(self) -> None:
        self.expected_stop = True
        task = self.task
        if task is None:
            return
        self.task = None
        if not task.done() and not self.failure.is_set():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return
