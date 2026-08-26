"""SoAI - Application runtime coordination and restart management [backend/app/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from app.runtime_banner_setup import ensure_banner_system
from app.runtime_config_reload_handling import (
    ApplicationRuntimeConfigReloadHandler,
    ApplicationRuntimeConfigReloadHandlerDependencies,
)
from app.runtime_dependencies import ApplicationRuntimeCoordinatorDependencies
from app.runtime_http_client_settings import extract_startup_http_client_section
from core.config.reload_coordinator import CoreConfigReloadCoordinator
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LogBannerSystemProtocol
from core.logging.rate_limited_logger import RateLimitedLogger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task

__all__ = ("ApplicationRuntimeCoordinator",)

OPERATION_APPLICATION_RUNTIME_CLOSE_COROUTINE_AFTER_UNSCHEDULED_TASK = (
    "application_runtime.schedule_background_task.close_coroutine_after_unscheduled_task"
)


class ApplicationRuntimeCoordinator:
    def __init__(self, deps: ApplicationRuntimeCoordinatorDependencies) -> None:
        self.deps = deps
        self.event_bus = deps.event_bus
        self.finalizer_tracker = deps.finalizer_tracker
        self._background_schedule_log_limiter = RateLimitedLogger(interval_seconds=10.0)
        self.startup_http_client_limits = extract_startup_http_client_section(
            deps.configuration,
            "MODELS.ROUTING.HTTP_CLIENT_LIMITS",
        )
        self.startup_http_client_timeouts = extract_startup_http_client_section(
            deps.configuration,
            "MODELS.ROUTING.HTTP_CLIENT_TIMEOUTS",
        )
        self.reload_coordinator = CoreConfigReloadCoordinator()
        self.config_reload_handler: ApplicationRuntimeConfigReloadHandler = (
            ApplicationRuntimeConfigReloadHandler(
                ApplicationRuntimeConfigReloadHandlerDependencies(
                    coordinator_dependencies=deps,
                    reload_coordinator=self.reload_coordinator,
                    startup_http_client_limits=self.startup_http_client_limits,
                    startup_http_client_timeouts=self.startup_http_client_timeouts,
                    require_restart=self.require_restart,
                    core_routing_applicator=deps.core_routing_applicator,
                ),
            )
        )

    async def require_restart(self, reason: str, source: str = "unknown") -> None:
        system_restart_requester = self.deps.runtime_state.system_restart_requester
        if system_restart_requester is None:
            raise StateError("System restart requester unavailable while requiring restart.")
        await system_restart_requester.require_restart(reason, source)

    def register_critical_shutdown(self, reason: str, exit_code: int = 1) -> None:
        runtime_state = self.deps.runtime_state
        text = reason.strip() if reason else "Critical failure"
        runtime_state.set_critical_shutdown(text, exit_code)

    def fail_startup(self, reason: str, exit_code: int = 1) -> None:
        self.register_critical_shutdown(reason, exit_code)
        raise SystemExit(exit_code)

    def ensure_banner_system(self) -> LogBannerSystemProtocol:
        self.deps, banner_system = ensure_banner_system(self.deps)
        return banner_system

    def get_active_event_loop(self) -> asyncio.AbstractEventLoop | None:
        event_loop = self.deps.runtime_state.async_loop
        if isinstance(event_loop, asyncio.AbstractEventLoop) and (not event_loop.is_closed()):
            return event_loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def schedule_background_task(
        self,
        coroutine: Coroutine[None, None, None],
        *,
        name: str | None = None,
    ) -> asyncio.Task[None] | None:
        event_loop = self.get_active_event_loop()
        if event_loop is None:
            task_name = self._resolve_background_task_name(coroutine, name, repr(coroutine))
            self._log_unscheduled_background_task(task_name, "no event loop is running")
            self._close_unscheduled_coroutine(coroutine, task_name)
            return None
        task_name = self._resolve_background_task_name(coroutine, name, "background-task")
        try:
            background_task = spawn_tracked_task(
                coroutine,
                loop=event_loop,
                name=task_name,
                logger=self.deps.logging.logger,
                cancellation_binder=self.deps.task_cancellation_binder,
                cancellation_id=create_system_id(
                    subsystem="application_runtime",
                    owner=task_name,
                    include_random_suffix=True,
                ),
                owner="application_runtime_background",
                finalizer_tracker=self.deps.finalizer_tracker,
            )
        except (RuntimeError, ValidationError):
            if not event_loop.is_closed():
                raise
            self._log_unscheduled_background_task(task_name, "the event loop closed")
            self._close_unscheduled_coroutine(coroutine, task_name)
            return None
        self.track_background_task(background_task)
        return background_task

    def _log_unscheduled_background_task(self, task_name: str, reason: str) -> None:
        should_emit, suppressed = self._background_schedule_log_limiter.should_emit()
        if not should_emit:
            return
        suffix = f" ({suppressed} similar messages suppressed)" if suppressed else ""
        self.deps.logging.logger.warning(
            "Unable to schedule background task '%s' because %s%s.",
            task_name,
            reason,
            suffix,
        )

    def _resolve_background_task_name(
        self,
        coroutine: Coroutine[None, None, None],
        name: str | None,
        fallback: str,
    ) -> str:
        if name is not None:
            return name
        try:
            return coroutine.__name__
        except AttributeError:
            return fallback

    def _close_unscheduled_coroutine(
        self,
        coroutine: Coroutine[None, None, None],
        task_name: str,
    ) -> None:
        try:
            coroutine.close()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self.deps.logging.logger,
                exception,
                message="Failed to close coroutine for unscheduled background task (non-critical).",
                operation=OPERATION_APPLICATION_RUNTIME_CLOSE_COROUTINE_AFTER_UNSCHEDULED_TASK,
                details={"task_name": task_name},
                level="debug",
            )

    def track_background_task(self, task: asyncio.Task[None]) -> None:
        if not isinstance(task, asyncio.Task):
            raise ValidationError("Background task must be an asyncio.Task.")
        self.finalizer_tracker.track_finalizer(task)

    def get_configuration_flag(self, key: str, default: bool) -> bool:
        config = self.deps.configuration
        if not config:
            return default
        return config.get_bool(key)
