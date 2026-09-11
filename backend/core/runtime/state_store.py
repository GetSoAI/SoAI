"""SoAI - Application runtime state store [backend/core/runtime/state_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading

from fastapi import FastAPI

from core.database.vacuum_result import DatabaseVacuumStartupResult
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from core.runtime.api_endpoint import RuntimeApiEndpoint
from core.runtime.protocols import RuntimePidLockProtocol
from core.state.protocols import (
    RestartStateManagerProtocol,
    SystemRestartRequesterProtocol,
)
from core.system.protocols import ManagedProcessProtocol

__all__ = ("RuntimeStateStore",)


class RuntimeStateStore:
    def __init__(
        self,
        *,
        startup_time: float,
        system_stop_event: asyncio.Event,
        restart_pending: asyncio.Event,
        startup_ready_event: asyncio.Event,
        shutdown_event: asyncio.Event,
        hardware_manager_available: bool,
        async_loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        self._startup_time = startup_time
        self._system_stop_event = system_stop_event
        self._restart_pending = restart_pending
        self._startup_ready_event = startup_ready_event
        self._shutdown_event = shutdown_event
        self._restart_state_manager: RestartStateManagerProtocol | None = None
        self._system_restart_requester: SystemRestartRequesterProtocol | None = None
        self._hardware_manager_available = hardware_manager_available
        self._degraded_mode = False
        self._database_maintenance = DatabaseVacuumStartupResult(status="not_run")
        self._repair_plane = False
        self._webui_available = False
        self._tls_user_supplied = False
        self._is_shutting_down = False
        self._restart_requested = False
        self._manual_shutdown_requested = False
        self._exit_code = 0
        self._critical_shutdown_reason: str | None = None
        self._pid_lock: RuntimePidLockProtocol | None = None
        self._async_loop = async_loop
        self._prune_tokens_task: asyncio.Task[None] | None = None
        self._runtime_api_endpoint: RuntimeApiEndpoint | None = None
        self._fastapi_app: FastAPI | None = None
        self._request_rate_limiter: MovingWindowRateLimiter | None = None
        self._transferred_processes: list[ManagedProcessProtocol] = []
        self._state_lock = threading.Lock()

    @property
    def startup_time(self) -> float:
        return self._startup_time

    @property
    def system_stop_event(self) -> asyncio.Event:
        return self._system_stop_event

    @property
    def restart_pending(self) -> asyncio.Event:
        return self._restart_pending

    @property
    def startup_ready_event(self) -> asyncio.Event:
        return self._startup_ready_event

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @property
    def restart_state_manager(self) -> RestartStateManagerProtocol | None:
        with self._state_lock:
            return self._restart_state_manager

    @property
    def system_restart_requester(self) -> SystemRestartRequesterProtocol | None:
        with self._state_lock:
            return self._system_restart_requester

    @property
    def hardware_manager_available(self) -> bool:
        with self._state_lock:
            return self._hardware_manager_available

    @property
    def degraded_mode(self) -> bool:
        with self._state_lock:
            return self._degraded_mode

    @property
    def repair_plane(self) -> bool:
        with self._state_lock:
            return self._repair_plane

    @property
    def webui_available(self) -> bool:
        with self._state_lock:
            return self._webui_available

    @property
    def tls_user_supplied(self) -> bool:
        with self._state_lock:
            return self._tls_user_supplied

    @property
    def is_shutting_down(self) -> bool:
        with self._state_lock:
            return self._is_shutting_down

    @property
    def restart_requested(self) -> bool:
        with self._state_lock:
            return self._restart_requested

    @property
    def manual_shutdown_requested(self) -> bool:
        with self._state_lock:
            return self._manual_shutdown_requested

    @property
    def exit_code(self) -> int:
        with self._state_lock:
            return self._exit_code

    @property
    def critical_shutdown_reason(self) -> str | None:
        with self._state_lock:
            return self._critical_shutdown_reason

    @property
    def pid_lock(self) -> RuntimePidLockProtocol | None:
        with self._state_lock:
            return self._pid_lock

    @property
    def async_loop(self) -> asyncio.AbstractEventLoop | None:
        with self._state_lock:
            return self._async_loop

    @property
    def prune_tokens_task(self) -> asyncio.Task[None] | None:
        with self._state_lock:
            return self._prune_tokens_task

    @property
    def runtime_api_endpoint(self) -> RuntimeApiEndpoint | None:
        with self._state_lock:
            return self._runtime_api_endpoint

    @property
    def fastapi_app(self) -> FastAPI | None:
        with self._state_lock:
            return self._fastapi_app

    @property
    def request_rate_limiter(self) -> MovingWindowRateLimiter | None:
        with self._state_lock:
            return self._request_rate_limiter

    @property
    def transferred_processes(self) -> tuple[ManagedProcessProtocol, ...]:
        with self._state_lock:
            return tuple(self._transferred_processes)

    def set_restart_state_manager(self, restart_state_manager: RestartStateManagerProtocol) -> None:
        with self._state_lock:
            self._restart_state_manager = restart_state_manager

    def set_system_restart_requester(
        self,
        system_restart_requester: SystemRestartRequesterProtocol,
    ) -> None:
        with self._state_lock:
            self._system_restart_requester = system_restart_requester

    def set_restart_required(self) -> None:
        with self._state_lock:
            self._restart_requested = True

    def set_server_runtime(
        self,
        *,
        runtime_api_endpoint: RuntimeApiEndpoint,
        tls_user_supplied: bool,
        fastapi_app: FastAPI | None = None,
        request_rate_limiter: MovingWindowRateLimiter | None = None,
    ) -> None:
        with self._state_lock:
            self._runtime_api_endpoint = runtime_api_endpoint
            self._tls_user_supplied = tls_user_supplied
            if fastapi_app is not None:
                self._fastapi_app = fastapi_app
            if request_rate_limiter is not None:
                self._request_rate_limiter = request_rate_limiter

    def set_webui_available(self, available: bool) -> None:
        with self._state_lock:
            self._webui_available = available

    def set_degraded_mode(self, enabled: bool) -> None:
        with self._state_lock:
            self._degraded_mode = enabled

    def set_repair_plane(self, enabled: bool) -> None:
        with self._state_lock:
            self._repair_plane = enabled

    def set_startup_ready(self) -> bool:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        with self._state_lock:
            if (
                self._is_shutting_down
                or self._shutdown_event.is_set()
                or self._system_stop_event.is_set()
            ):
                return False
            event_loop = self._async_loop
            if event_loop is None:
                self._startup_ready_event.set()
                return True
            if event_loop.is_closed():
                return False
            if running_loop is event_loop:
                self._startup_ready_event.set()
                return True
            try:
                event_loop.call_soon_threadsafe(self._set_startup_ready_from_loop)
            except RuntimeError:
                return False
            return True

    def _set_startup_ready_from_loop(self) -> None:
        with self._state_lock:
            if (
                self._is_shutting_down
                or self._shutdown_event.is_set()
                or self._system_stop_event.is_set()
            ):
                return
            self._startup_ready_event.set()

    def set_critical_shutdown(self, reason: str, exit_code: int) -> None:
        with self._state_lock:
            text = reason.strip() if reason else "Critical failure"
            if self._critical_shutdown_reason is None:
                self._critical_shutdown_reason = text
            if exit_code != 0:
                self._exit_code = exit_code

    def set_manual_shutdown_requested(self) -> None:
        with self._state_lock:
            self._manual_shutdown_requested = True

    def begin_shutdown(self) -> bool:
        with self._state_lock:
            if self._is_shutting_down:
                return False
            self._is_shutting_down = True
            return True

    def set_system_stop(self) -> None:
        self._set_stop_event(self._system_stop_event)

    def set_shutdown_requested(self) -> None:
        self._set_stop_event(self._shutdown_event)

    def set_pid_lock(self, pid_lock: RuntimePidLockProtocol | None) -> None:
        with self._state_lock:
            self._pid_lock = pid_lock

    def set_prune_tokens_task(self, task: asyncio.Task[None] | None) -> None:
        with self._state_lock:
            self._prune_tokens_task = task

    def transfer_process_ownership(self, process_handle: ManagedProcessProtocol) -> None:
        with self._state_lock:
            self._transferred_processes.append(process_handle)

    def _set_stop_event(self, event: asyncio.Event) -> None:
        def apply_stop_event() -> None:
            self._startup_ready_event.clear()
            event.set()

        event_loop = self.async_loop
        if event_loop is not None and not event_loop.is_closed():
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop is event_loop:
                apply_stop_event()
                return
            try:
                event_loop.call_soon_threadsafe(apply_stop_event)
            except RuntimeError:
                apply_stop_event()
            return
        apply_stop_event()

    @property
    def database_maintenance(self) -> DatabaseVacuumStartupResult:
        with self._state_lock:
            return self._database_maintenance

    def set_database_maintenance(self, result: DatabaseVacuumStartupResult) -> None:
        with self._state_lock:
            self._database_maintenance = result
