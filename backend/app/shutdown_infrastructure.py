"""SoAI - Application shutdown infrastructure finalization [backend/app/shutdown_infrastructure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.lifecycle.failure_recording import record_critical_lifecycle_failures
from app.lifecycle.results import LifecycleFailure
from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.shutdown_infrastructure_plan import (
    build_event_bus_shutdown_entries,
    build_http_client_and_database_shutdown_entries,
)
from app.types_application import ApplicationContext
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS

__all__ = (
    "await_task_finalizers",
    "shutdown_event_bus",
    "shutdown_http_client_and_database",
)

OPERATION_AWAIT_TASK_FINALIZERS = "app.shutdown_infrastructure.await_task_finalizers"


async def shutdown_event_bus(
    *,
    application_context: ApplicationContext,
    timeout_sec: float,
) -> None:
    entries = build_event_bus_shutdown_entries(
        application_context,
        component_timeout_sec=timeout_sec,
    )
    failures = await LifecycleRunner(
        logger=application_context.logging.logger,
    ).run_entries_continue(entries)
    record_critical_lifecycle_failures(application_context, failures)


async def await_task_finalizers(
    *,
    application_context: ApplicationContext,
    timeout_sec: float,
) -> None:
    finalizer_tracker = application_context.services.tasks.task_finalizer_tracker
    try:
        completed = await finalizer_tracker.await_all_finalizers(
            timeout=timeout_sec,
            logger=application_context.logging.logger,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        message = (
            "Task finalizer wait failed during shutdown: "
            f"{type(exception).__name__}: {exception}"
        )
        log_exception(
            application_context.logging.logger,
            exception,
            message=message,
            operation=OPERATION_AWAIT_TASK_FINALIZERS,
            level="critical",
        )
        _record_task_finalizer_failure(application_context, message)
        return
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        message = (
            "Task finalizer wait failed unexpectedly during shutdown: "
            f"{type(exception).__name__}: {exception}"
        )
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_AWAIT_TASK_FINALIZERS,
        )
        log_exception(
            application_context.logging.logger,
            coerced,
            message=message,
            operation=OPERATION_AWAIT_TASK_FINALIZERS,
            level="critical",
        )
        _record_task_finalizer_failure(application_context, message)
        return
    if completed:
        return
    _record_task_finalizer_failure(
        application_context,
        "Timed out while waiting for linked task finalizers during shutdown.",
    )


def _record_task_finalizer_failure(
    application_context: ApplicationContext,
    message: str,
) -> None:
    record_critical_lifecycle_failures(
        application_context,
        [
            LifecycleFailure(
                component_name="Task Finalizers",
                phase="shutdown",
                critical=True,
                message=message,
            ),
        ],
    )


async def shutdown_http_client_and_database(
    *,
    application_context: ApplicationContext,
    timeout_sec: float,
) -> None:
    application_context.logging.logger.debug("Shutting down HTTP client and database...")
    entries = build_http_client_and_database_shutdown_entries(
        application_context,
        component_timeout_sec=timeout_sec,
    )
    failures = await LifecycleRunner(
        logger=application_context.logging.logger,
    ).run_entries_continue(entries)
    record_critical_lifecycle_failures(application_context, failures)
