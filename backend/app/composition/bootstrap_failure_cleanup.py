"""SoAI - Bootstrap failure cleanup for partial application assembly [backend/app/composition/bootstrap_failure_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.bootstrap_resource_cleanup_entries import (
    bootstrap_resource_cleanup_entries,
)
from app.lifecycle.runner import LifecycleRunner
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    import httpx2

    from app.composition.build_application_bootstrap_core import CoreBootstrapStage
    from app.composition.build_tasks import TaskRegistryFactoryResult
    from app.config.service import ConfigManager
    from app.types_services_database import DatabaseServices
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "cleanup_database_task_bootstrap_failure",
    "cleanup_failed_bootstrap",
)


async def cleanup_failed_bootstrap(
    *,
    phase: str = "bootstrap_failure_cleanup",
    core_stage: CoreBootstrapStage | None,
    database_services: DatabaseServices | None,
    config_manager: ConfigManager | None,
    task_registry_result: TaskRegistryFactoryResult | None,
    http_client: httpx2.AsyncClient | None,
    logger: LoggerProtocol,
) -> None:
    task_registry = task_registry_result.registry if task_registry_result is not None else None
    event_bus = core_stage.event_bus if core_stage is not None else None
    entries = bootstrap_resource_cleanup_entries(
        phase=phase,
        timeout_sec=CONTROL_TIMEOUT_SEC,
        task_registry=task_registry,
        config_manager=config_manager,
        http_client=http_client,
        database_services=database_services,
        event_bus=event_bus,
    )
    failures = await LifecycleRunner(logger=logger).run_entries_continue(entries)
    if failures:
        logger.critical(
            "Bootstrap failure cleanup completed with %d failure(s).",
            len(failures),
        )


async def cleanup_database_task_bootstrap_failure(
    database_services: DatabaseServices | None,
    config_manager: ConfigManager | None,
    task_registry_result: TaskRegistryFactoryResult | None,
    http_client: httpx2.AsyncClient | None,
    logger: LoggerProtocol,
) -> None:
    await cleanup_failed_bootstrap(
        phase="database_task_bootstrap_failure_cleanup",
        core_stage=None,
        database_services=database_services,
        config_manager=config_manager,
        task_registry_result=task_registry_result,
        http_client=http_client,
        logger=logger,
    )
