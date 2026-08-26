"""SoAI - Startup wait for initial model discovery [backend/app/startup_steps/actors_and_services_model_discovery_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exceptions import StateError
from core.runtime.startup_status import StartupPhaseStatus

if TYPE_CHECKING:
    from app.application_dependencies import ApplicationLogging
    from app.types_application import ApplicationContext
    from core.config.protocols import ConfigProtocol
    from core.models.protocols import ModelManagerProtocol

__all__ = ("wait_for_model_discovery_or_shutdown",)

STARTUP_DISCOVERY_PROGRESS_LOG_DELAY_SEC = 31.0


async def wait_for_model_discovery_or_shutdown(
    *,
    application_context: ApplicationContext,
    configuration: ConfigProtocol,
    model_manager_instance: ModelManagerProtocol,
    logging_context: ApplicationLogging,
) -> bool:
    _ = configuration
    discovery_complete_event = model_manager_instance.startup_discovery_complete_event
    discovery_wait_task = create_ephemeral_task(
        discovery_complete_event.wait(),
        name="startup-model-discovery",
    )
    shutdown_wait_task = create_ephemeral_task(
        application_context.runtime.shutdown_event.wait(),
        name="startup-model-discovery-shutdown",
    )
    system_stop_wait_task = create_ephemeral_task(
        application_context.runtime.system_stop_event.wait(),
        name="startup-model-discovery-system-stop",
    )
    wait_started_at = asyncio.get_running_loop().time()
    reminder_logged = False
    pending: set[asyncio.Task[Literal[True]]] = {
        discovery_wait_task,
        shutdown_wait_task,
        system_stop_wait_task,
    }
    done: set[asyncio.Task[Literal[True]]] = set()
    while pending:
        elapsed = asyncio.get_running_loop().time() - wait_started_at
        wait_timeout = STARTUP_DISCOVERY_PROGRESS_LOG_DELAY_SEC
        if not reminder_logged:
            reminder_remaining = STARTUP_DISCOVERY_PROGRESS_LOG_DELAY_SEC - elapsed
            if reminder_remaining <= 0.0:
                reminder_logged = True
                logging_context.logger.info(
                    "Initial model discovery is still in progress after %.0f seconds. Scanning installed models; please wait...",
                    STARTUP_DISCOVERY_PROGRESS_LOG_DELAY_SEC,
                )
                logging_context.gui_status("Still discovering available models...")
                continue
            wait_timeout = reminder_remaining
        done, pending = await asyncio.wait(
            pending,
            timeout=wait_timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if done:
            break
        if not reminder_logged:
            reminder_logged = True
            logging_context.logger.info(
                "Initial model discovery is still in progress after %.0f seconds. Scanning installed models; please wait...",
                STARTUP_DISCOVERY_PROGRESS_LOG_DELAY_SEC,
            )
            logging_context.gui_status("Still discovering available models...")
    await cancel_and_await(pending, timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC)
    if shutdown_wait_task in done or system_stop_wait_task in done:
        logging_context.logger.info("Startup model discovery wait interrupted by shutdown request.")
        return True
    result = model_manager_instance.startup_discovery_result
    if result.status is StartupPhaseStatus.FAILED:
        raise StateError(
            "Initial model discovery failed.",
            operation="startup.wait_for_model_discovery_or_shutdown",
            details={"startup_discovery_result": result.message},
        )
    if result.status is StartupPhaseStatus.CANCELLED_BY_SHUTDOWN:
        logging_context.logger.info("Startup model discovery was cancelled by shutdown request.")
        return True
    if result.status is StartupPhaseStatus.PENDING:
        raise StateError(
            "Initial model discovery completed without a terminal startup result.",
            operation="startup.wait_for_model_discovery_or_shutdown",
        )
    if result.status is not StartupPhaseStatus.SUCCESS:
        raise StateError(
            "Initial model discovery completed with an unknown startup result.",
            operation="startup.wait_for_model_discovery_or_shutdown",
        )
    logging_context.logger.debug("Initial model discovery complete.")
    logging_context.gui_status("Model discovery complete")
    return False
