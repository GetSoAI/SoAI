"""SoAI - Central lifecycle entry runner [backend/app/lifecycle/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.lifecycle.entries import LifecycleEntry
from app.lifecycle.results import LifecycleFailure, LifecycleRunError
from core.concurrency.cancellation_cleanup import current_task_has_pending_cancellation
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("LifecycleRunner",)

OPERATION_LIFECYCLE_RUN_ENTRY = "app.lifecycle.runner.run_entry"


class LifecycleRunner:
    def __init__(self, *, logger: LoggerProtocol) -> None:
        self._logger = logger

    async def run_entries(self, entries: tuple[LifecycleEntry, ...]) -> list[LifecycleFailure]:
        failures: list[LifecycleFailure] = []
        for entry in entries:
            failure = await self.run_entry(entry)
            if failure is None:
                continue
            failures.append(failure)
            if entry.critical:
                raise LifecycleRunError(failure)
        return failures

    async def run_entries_continue(
        self,
        entries: tuple[LifecycleEntry, ...],
    ) -> list[LifecycleFailure]:
        failures: list[LifecycleFailure] = []
        for entry in entries:
            failure = await self.run_entry(entry)
            if failure is not None:
                failures.append(failure)
        return failures

    async def run_entry(self, entry: LifecycleEntry) -> LifecycleFailure | None:
        try:
            self._logger.debug(
                "Running lifecycle phase '%s' for %s.",
                entry.phase,
                entry.component_name,
            )
            if entry.timeout_sec == 0:
                await entry.action()
            else:
                await asyncio.wait_for(entry.action(), timeout=entry.timeout_sec)
            return None
        except asyncio.CancelledError as exception:
            if current_task_has_pending_cancellation():
                raise
            message = (
                f"Lifecycle phase '{entry.phase}' was cancelled unexpectedly for "
                f"{entry.component_name}."
            )
            log_exception(
                self._logger,
                exception,
                message=message,
                operation=OPERATION_LIFECYCLE_RUN_ENTRY,
                level="critical" if entry.critical else "warning",
            )
            return LifecycleFailure(
                component_name=entry.component_name,
                phase=entry.phase,
                critical=entry.critical,
                message=message,
            )
        except TimeoutError:
            message = (
                f"Lifecycle phase '{entry.phase}' timed out for {entry.component_name} "
                f"after {entry.timeout_sec:.1f}s."
            )
            if entry.critical:
                self._logger.critical(message)
            else:
                self._logger.warning(message)
            return LifecycleFailure(
                component_name=entry.component_name,
                phase=entry.phase,
                critical=entry.critical,
                message=message,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            message = (
                f"Lifecycle phase '{entry.phase}' failed for {entry.component_name}: "
                f"{type(exception).__name__}: {exception}"
            )
            log_exception(
                self._logger,
                exception,
                message=message,
                operation=OPERATION_LIFECYCLE_RUN_ENTRY,
                level="critical" if entry.critical else "warning",
            )
            return LifecycleFailure(
                component_name=entry.component_name,
                phase=entry.phase,
                critical=entry.critical,
                message=message,
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_LIFECYCLE_RUN_ENTRY,
            )
            message = (
                f"Lifecycle phase '{entry.phase}' failed unexpectedly for "
                f"{entry.component_name}: {type(exception).__name__}: {exception}"
            )
            log_exception(
                self._logger,
                coerced,
                message=message,
                operation=OPERATION_LIFECYCLE_RUN_ENTRY,
                level="critical" if entry.critical else "warning",
            )
            return LifecycleFailure(
                component_name=entry.component_name,
                phase=entry.phase,
                critical=entry.critical,
                message=message,
            )
