"""SoAI - Application cancellation bootstrap settings [backend/app/bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.application_dependencies import ApplicationBootstrapModuleDependencies
from app.composition.build_cancellation_system import CancellationSystem
from core.config.protocols import ConfigProtocol
from core.logging.protocols import LoggerProtocol

__all__ = ("apply_cancellation_system_settings",)


async def apply_cancellation_system_settings(
    config: ConfigProtocol,
    cancellation_system: CancellationSystem,
    lifecycle_logger: LoggerProtocol,
    module_dependencies: ApplicationBootstrapModuleDependencies,
) -> None:
    if cancellation_system is None or config is None:
        return
    coerce_positive_int = module_dependencies.coerce_positive_int
    task_manager_config = config.get("SYSTEM.TASKS", {})
    if not isinstance(task_manager_config, dict):
        task_manager_config = {}
    history_limit_value = task_manager_config.get("CANCELLATION_HISTORY_LIMIT")
    listener_queue_value = task_manager_config.get("CANCELLATION_LISTENER_QUEUE_SIZE")
    history_limit = None
    listener_limit = None
    if history_limit_value is not None:
        history_limit = coerce_positive_int(
            history_limit_value,
            default=cancellation_system.history.history_limit,
            minimum=1,
            label="SYSTEM.TASKS.CANCELLATION_HISTORY_LIMIT",
            logger=lifecycle_logger,
        )
    if listener_queue_value is not None:
        listener_limit = coerce_positive_int(
            listener_queue_value,
            default=cancellation_system.event_bus.get_queue_size(),
            minimum=1,
            label="SYSTEM.TASKS.CANCELLATION_LISTENER_QUEUE_SIZE",
            logger=lifecycle_logger,
        )
    if history_limit is not None:
        active_scopes = await cancellation_system.token_collection.get_all_scope_ids(
            include_internal=True,
        )
        await cancellation_system.history.update_limit(
            history_limit,
            active_scopes=set(active_scopes),
        )
    if listener_limit is not None:
        cancellation_system.event_bus.update_queue_size(listener_limit)
