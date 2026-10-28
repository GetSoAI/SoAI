"""SoAI - Plugin configuration mutation lock ownership and contention diagnostics [backend/app/config/plugin_config_mutation_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from filelock import Timeout

from core.config.locks import PluginConfigurationBusyError, get_plugin_config_mutation_lock_path
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.files.locking import async_guarded_file_lock
from core.logging.rate_limited_logger import RateLimitedLogger
from core.runtime.soai_identifiers import create_system_id
from core.timing.durations import seconds_to_ms

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "PLUGIN_CONFIG_MUTATION_LOCK_TIMEOUT_SECONDS",
    "PluginConfigMutationLock",
    "PluginConfigMutationLockDependencies",
)

PLUGIN_CONFIG_MUTATION_LOCK_TIMEOUT_SECONDS = 30.0
SLOW_WAIT_DIAGNOSTIC_MS = 1000
SLOW_HOLD_DIAGNOSTIC_MS = 5000
CONTENTION_DIAGNOSTIC_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class PluginConfigMutationLockDependencies:
    plugins_path: str | None
    lock_directory: str | None
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(owner="PluginConfigMutationLockDependencies", logger=self.logger)


@dataclass(frozen=True, slots=True)
class _MutationHolder:
    config_name: str
    operation: str
    task_name: str | None
    correlation_id: str
    acquired_at_monotonic: float

    def details(self, *, now: float) -> JSONDict:
        return {
            "holder_config_name": self.config_name,
            "holder_operation": self.operation,
            "holder_task": self.task_name,
            "holder_correlation_id": self.correlation_id,
            "holder_held_ms": seconds_to_ms(now - self.acquired_at_monotonic),
        }


class PluginConfigMutationLock:
    def __init__(self, deps: PluginConfigMutationLockDependencies) -> None:
        self._deps = deps
        self._holder: _MutationHolder | None = None
        self._contention_diagnostics = RateLimitedLogger(
            interval_seconds=CONTENTION_DIAGNOSTIC_INTERVAL_SECONDS
        )

    @asynccontextmanager
    async def scope(
        self,
        config_name: str,
        *,
        operation: str,
        deadline: MonotonicDeadline | None,
    ) -> AsyncGenerator[None]:
        normalized_name = config_name.strip()
        if not normalized_name:
            raise ValidationError("Plugin config mutation requires a config name.")
        if normalized_name == "core":
            yield
            return
        if not self._deps.plugins_path:
            raise StateError("Plugin directory is not configured.")
        current_task = asyncio.current_task()
        task_name = current_task.get_name() if current_task is not None else None
        correlation_id = create_system_id(
            subsystem="plugin-config-mutation", include_random_suffix=True
        )
        timeout_seconds = PLUGIN_CONFIG_MUTATION_LOCK_TIMEOUT_SECONDS
        if deadline is not None:
            timeout_seconds = min(timeout_seconds, deadline.remaining_seconds())
        requested: JSONDict = {
            "config_name": normalized_name,
            "operation": operation,
            "task": task_name,
            "correlation_id": correlation_id,
        }
        wait_started = time.monotonic()

        def busy(exception: Timeout) -> PluginConfigurationBusyError:
            details = self._contention_details(requested, wait_started=wait_started)
            self._report_contention("Plugin configuration mutation lock is busy.", details)
            return PluginConfigurationBusyError(
                "Plugin configuration mutation lock acquisition timed out.",
                details=details,
                operation=operation,
                cause=exception,
            )

        async with async_guarded_file_lock(
            get_plugin_config_mutation_lock_path(
                self._deps.plugins_path, lock_directory=self._deps.lock_directory
            ),
            timeout=timeout_seconds,
            on_timeout=busy,
        ):
            holder = _MutationHolder(
                config_name=normalized_name,
                operation=operation,
                task_name=task_name,
                correlation_id=correlation_id,
                acquired_at_monotonic=time.monotonic(),
            )
            self._holder = holder
            try:
                yield
            finally:
                if self._holder is holder:
                    self._holder = None
                self._record_release(requested, holder, wait_started=wait_started)

    def _contention_details(self, requested: JSONDict, *, wait_started: float) -> JSONDict:
        now = time.monotonic()
        details: JSONDict = {**requested, "wait_ms": seconds_to_ms(now - wait_started)}
        holder = self._holder
        if holder is not None:
            details.update(holder.details(now=now))
        return details

    def _record_release(
        self, requested: JSONDict, holder: _MutationHolder, *, wait_started: float
    ) -> None:
        released_at = time.monotonic()
        wait_ms = seconds_to_ms(holder.acquired_at_monotonic - wait_started)
        hold_ms = seconds_to_ms(released_at - holder.acquired_at_monotonic)
        details: JSONDict = {**requested, "wait_ms": wait_ms, "hold_ms": hold_ms}
        if wait_ms >= SLOW_WAIT_DIAGNOSTIC_MS or hold_ms >= SLOW_HOLD_DIAGNOSTIC_MS:
            self._report_contention("Plugin configuration mutation lock was contended.", details)
            return
        self._deps.logger.debug(
            "Plugin configuration mutation lock released: %s", _format_details(details)
        )

    def _report_contention(self, message: str, details: JSONDict) -> None:
        emit, suppressed = self._contention_diagnostics.should_emit()
        if not emit:
            self._deps.logger.debug("%s %s", message, _format_details(details))
            return
        self._deps.logger.warning(
            "%s %s suppressed_since_last=%s", message, _format_details(details), suppressed
        )


def _format_details(details: JSONDict) -> str:
    return " ".join(f"{key}={value}" for key, value in details.items())
