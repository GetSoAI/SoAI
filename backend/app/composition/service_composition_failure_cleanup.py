"""SoAI - Service composition failure cleanup [backend/app/composition/service_composition_failure_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.composition.application_bootstrap_state import ApplicationBootstrapState
from app.composition.bootstrap_resource_cleanup_entries import (
    bootstrap_resource_cleanup_entries,
)
from app.lifecycle.runner import LifecycleRunner
from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    shutdown_bounded_pool_executor,
)
from core.logging.protocols import LoggerProtocol
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("cleanup_failed_service_composition",)


async def cleanup_failed_service_composition(
    *,
    bootstrap_state: ApplicationBootstrapState,
    logger: LoggerProtocol,
    login_password_pool: BoundedBlockingPool | None,
) -> None:
    entries = bootstrap_resource_cleanup_entries(
        phase="service_composition_failure_cleanup",
        timeout_sec=CONTROL_TIMEOUT_SEC,
        task_registry=bootstrap_state.task_registry,
        config_manager=bootstrap_state.config_manager,
        http_client=bootstrap_state.infrastructure_services.http_client,
        database_services=bootstrap_state.database_services,
        event_bus=bootstrap_state.event_bus,
    )
    try:
        failures = await LifecycleRunner(logger=logger).run_entries_continue(entries)
        if failures:
            logger.critical(
                "Service composition failure cleanup completed with %d failure(s).",
                len(failures),
            )
    finally:
        bootstrap_state.infrastructure_services.prompt_token_counter.shutdown()
        if login_password_pool is not None:
            shutdown_bounded_pool_executor(login_password_pool)
