"""SoAI - Shutdown stage error boundary runner [backend/app/lifecycle/shutdown_stage_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.lifecycle.failure_recording import record_critical_lifecycle_failures
from app.lifecycle.results import LifecycleFailure
from app.types_application import ApplicationContext
from core.concurrency.cancellation_cleanup import current_task_has_pending_cancellation
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS

__all__ = ("run_shutdown_stage_continue", "run_sync_shutdown_stage_continue")

OPERATION_RUN_SHUTDOWN_STAGE = "app.lifecycle.shutdown_stage_runner.run_shutdown_stage"


async def run_shutdown_stage_continue(
    *,
    application_context: ApplicationContext,
    component_name: str,
    awaitable: Awaitable[None],
) -> None:
    try:
        await awaitable
    except asyncio.CancelledError as exception:
        if current_task_has_pending_cancellation():
            raise
        message = f"Shutdown stage was cancelled unexpectedly for {component_name}."
        log_exception(
            application_context.logging.logger,
            exception,
            message=message,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
            level="critical",
        )
        _record_shutdown_stage_failure(application_context, component_name, message)
    except RECOVERABLE_EXCEPTIONS as exception:
        message = (
            f"Shutdown stage failed for {component_name}: "
            f"{type(exception).__name__}: {exception}"
        )
        log_exception(
            application_context.logging.logger,
            exception,
            message=message,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
            level="critical",
        )
        _record_shutdown_stage_failure(application_context, component_name, message)
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        message = (
            f"Shutdown stage failed unexpectedly for {component_name}: "
            f"{type(exception).__name__}: {exception}"
        )
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
        )
        log_exception(
            application_context.logging.logger,
            coerced,
            message=message,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
            level="critical",
        )
        _record_shutdown_stage_failure(application_context, component_name, message)


def run_sync_shutdown_stage_continue(
    *,
    application_context: ApplicationContext,
    component_name: str,
    action: Callable[[], None],
) -> None:
    try:
        action()
    except RECOVERABLE_EXCEPTIONS as exception:
        message = (
            f"Shutdown stage failed for {component_name}: "
            f"{type(exception).__name__}: {exception}"
        )
        log_exception(
            application_context.logging.logger,
            exception,
            message=message,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
            level="critical",
        )
        _record_shutdown_stage_failure(application_context, component_name, message)
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        message = (
            f"Shutdown stage failed unexpectedly for {component_name}: "
            f"{type(exception).__name__}: {exception}"
        )
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
        )
        log_exception(
            application_context.logging.logger,
            coerced,
            message=message,
            operation=OPERATION_RUN_SHUTDOWN_STAGE,
            level="critical",
        )
        _record_shutdown_stage_failure(application_context, component_name, message)


def _record_shutdown_stage_failure(
    application_context: ApplicationContext,
    component_name: str,
    message: str,
) -> None:
    record_critical_lifecycle_failures(
        application_context,
        [
            LifecycleFailure(
                component_name=component_name,
                phase="shutdown",
                critical=True,
                message=message,
            ),
        ],
    )
