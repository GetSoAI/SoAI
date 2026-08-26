"""SoAI - Config manager lifecycle operations [backend/app/config/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.config.internal_protocols import ConfigManagerLifecycleService
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import (
    TriggerConfigReconciliationCommand,
    TriggerConfigScanCommand,
    UpdateConfigCommand,
)
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.progress import create_periodic_task

__all__ = (
    "establish_config_baseline",
    "shutdown_config_manager",
    "start_config_manager",
    "trigger_config_scan",
    "unsubscribe_config_commands",
)

OPERATION = "config_manager.start"


def start_config_manager(service: ConfigManagerLifecycleService) -> None:
    if service.shutdown_event.is_set():
        raise StateError("ConfigManager cannot be started after shutdown.")
    if service.subscriptions_registered:
        return
    polling_interval_ms = service.config.get_int("SYSTEM.CONFIG.POLLING_INTERVAL_MS")
    polling_interval_seconds = max(0.001, float(polling_interval_ms) / 1000.0)
    try:
        service.event_bus.subscribe(
            TriggerConfigReconciliationCommand,
            service.command_handlers.handle_reconciliation_trigger,
        )
        service.event_bus.subscribe(
            TriggerConfigScanCommand,
            service.command_handlers.handle_scan_trigger,
        )
        service.event_bus.subscribe(
            UpdateConfigCommand,
            service.command_handlers.handle_update_config_command,
        )
        service.subscriptions_registered = True
        polling_task = create_periodic_task(
            shutdown_event=service.shutdown_event,
            interval_seconds=polling_interval_seconds,
            task=service.perform_periodic_scan,
            cancellation_binder=service.cancellation_binder,
            finalizer_tracker=service.finalizer_tracker,
            logger=service.logger,
            managed_task_name="config-manager-poll",
            periodic_task_name="config_reconciliation",
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "config_manager",
                    "reconciliation",
                    safe_or_hashed_segment(str(id(service))),
                ),
            ),
            owner="config_polling",
            metadata={"interval_ms": int(max(1, int(polling_interval_ms)))},
        )
        _ = service.periodic_tasks.track(polling_task)
        service.logger.debug("Configuration Manager actor started.")
    except RECOVERABLE_EXCEPTIONS as exception:
        if service.subscriptions_registered:
            unsubscribe_config_commands(service)
            service.subscriptions_registered = False
        coerced = coerce_to_soai_error(
            exception,
            operation="config_manager.start",
        )
        log_exception(
            service.logger,
            coerced,
            message="Failed to start ConfigManager.",
            operation=OPERATION,
        )
        raise coerced from exception


async def shutdown_config_manager(service: ConfigManagerLifecycleService) -> None:
    if service.shutdown_event.is_set():
        return
    service.logger.debug("ConfigManager shutdown initiated.")
    service.shutdown_event.set()
    if service.subscriptions_registered:
        unsubscribe_config_commands(service)
        service.subscriptions_registered = False
    await service.periodic_tasks.cancel(message="Cancelling config manager periodic tasks...")
    service.logger.debug("Configuration Manager actor stopped.")
    service.logger.debug("Tracked configuration lock files remain in place for concurrent safety.")


async def establish_config_baseline(service: ConfigManagerLifecycleService) -> None:
    if not service.reconciler.initial_baseline_established:
        service.logger.info("Loading configuration, please wait...")
        await service.reconciler.reconcile_filesystem_state(
            update_baseline=True,
            delete_from_cache=service.delete_from_cache,
        )
        service.logger.info("Initial configuration baseline established.")
        return
    service.logger.info(
        "Initial configuration baseline was already established by another process.",
    )


async def trigger_config_scan(
    service: ConfigManagerLifecycleService,
    *,
    config_name: str | None,
    source: str,
) -> None:
    await service.reconciler.scan_filesystem_state(
        emit_events=True,
        source=source,
        config_name=config_name,
        delete_from_cache=service.delete_from_cache,
    )


def unsubscribe_config_commands(service: ConfigManagerLifecycleService) -> None:
    service.event_bus.unsubscribe(
        TriggerConfigReconciliationCommand,
        service.command_handlers.handle_reconciliation_trigger,
    )
    service.event_bus.unsubscribe(
        TriggerConfigScanCommand,
        service.command_handlers.handle_scan_trigger,
    )
    service.event_bus.unsubscribe(
        UpdateConfigCommand,
        service.command_handlers.handle_update_config_command,
    )
