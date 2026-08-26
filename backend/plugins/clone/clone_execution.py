"""SoAI - Journaled plugin clone execution [backend/plugins/clone/clone_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX, PLUGIN_FILE_SUFFIX
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from plugins.clone.clone_materialization import materialize_clone
from plugins.clone.clone_plan import ClonePlan
from plugins.clone.clone_planning import resolve_clone_plan
from plugins.clone.clone_rollback import rollback_clone_transaction
from plugins.clone.clone_storage_reservation import acquire_clone_storage_reservation
from plugins.clone.operation_locks import clone_operation_locks
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.protocols_internal.task_progress.internal_protocols import TaskProgressSenderProtocol

if TYPE_CHECKING:
    from core.events.types_base import Event

__all__ = ("cleanup_failed_clone", "execute_clone")

LOGGER_NAME = "SoAI.plugins.clone.clone_execution"
OPERATION_STORAGE_RESERVATION_RELEASE = "plugin_clone.storage_reservation_release"
CLONE_EXECUTION_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


async def _ensure_clone_target_is_available(
    plugin_manager: PluginManagerRuntimeProtocol,
    plan: ClonePlan,
) -> None:
    if (
        await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
            plan.target_plugin_name
        )
        is not None
    ):
        raise ValidationError(f"A plugin named '{plan.target_plugin_name}' already exists.")
    target_config_file = os.path.join(
        plugin_manager.paths.plugin_directory,
        f"{plan.target_plugin_name}{PLUGIN_CONFIG_FILE_SUFFIX}",
    )
    for path in (plan.target_plugin_file, target_config_file, plan.target_models_path):
        if path and await async_path_exists(path):
            raise ValidationError(f"Clone target path already exists: {path}")


async def _ensure_clone_source_is_available(
    plugin_manager: PluginManagerRuntimeProtocol,
    plan: ClonePlan,
) -> None:
    source_record = await plugin_manager.dependencies.databases.plugins.get_plugin_by_name(
        plan.source_plugin_name
    )
    source_file = os.path.join(
        plugin_manager.paths.plugin_directory,
        f"{plan.source_plugin_name}{PLUGIN_FILE_SUFFIX}",
    )
    if source_record is None or not await async_path_exists(source_file):
        raise ValidationError(f"Source plugin '{plan.source_plugin_name}' no longer exists.")


async def execute_clone(
    plugin_manager: PluginManagerRuntimeProtocol,
    *,
    source_plugin_name: str,
    reserved_target_name: str,
    clone_models: bool,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    field_overrides: JSONDict | None,
    context: RequestContext | None,
    progress_callback: TaskProgressSenderProtocol,
    fencing_token: int,
) -> tuple[ClonePlan, str]:
    async with clone_operation_locks(
        plugin_manager,
        (source_plugin_name, reserved_target_name),
        mutation_task_id=task_id,
        mutation_fencing_token=fencing_token,
    ):
        storage_reservation = None
        release_storage_reservation = False
        try:
            config_manager = plugin_manager.dependencies.infrastructure.config_manager
            async with config_manager.plugin_config_mutation_scope(source_plugin_name):
                configuration_snapshot = await config_manager.build_clone_configuration_snapshot(
                    source_plugin_name,
                    field_overrides,
                )
                if configuration_snapshot is None:
                    raise ValidationError(
                        f"Source plugin '{source_plugin_name}' configuration is unavailable."
                    )
                source_config, cloned_config = configuration_snapshot
                plan = await resolve_clone_plan(
                    plugin_manager,
                    source_plugin_name=source_plugin_name,
                    target_name=reserved_target_name,
                    clone_models=clone_models,
                    field_overrides=field_overrides,
                    source_config=source_config,
                    progress_callback=progress_callback,
                    reservation_task_id=task_id,
                )
            if plan.target_plugin_name != reserved_target_name:
                raise ValidationError("Clone planning changed the atomically reserved target.")
            transitioned = (
                await plugin_manager.dependencies.databases.plugins.clone_transactions.transition(
                    task_id,
                    "admitted",
                    "staging",
                )
            )
            if not transitioned:
                raise ValidationError("Clone transaction could not enter staging.")
            await _ensure_clone_source_is_available(plugin_manager, plan)
            await _ensure_clone_target_is_available(plugin_manager, plan)
            storage_reservation = await acquire_clone_storage_reservation(
                plugin_manager,
                plan,
                cloned_config,
            )
            message = await materialize_clone(
                plugin_manager,
                plan=plan,
                reply_channel=reply_channel,
                task_id=task_id,
                cloned_config=cloned_config,
                progress_callback=progress_callback,
                storage_reservation=storage_reservation,
                fencing_token=fencing_token,
                context=context,
            )
            release_storage_reservation = True
        except CLONE_EXECUTION_EXCEPTIONS:
            await uncancel_and_wait(rollback_clone_transaction(plugin_manager, task_id=task_id))
            release_storage_reservation = True
            raise
        finally:
            if storage_reservation is not None and release_storage_reservation:
                try:
                    await storage_reservation.release()
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Clone storage reservation release failed; stale-reservation recovery remains active.",
                        operation=OPERATION_STORAGE_RESERVATION_RELEASE,
                        details={"task_id": task_id},
                        level="warning",
                    )
    return (plan, message)


async def cleanup_failed_clone(
    plugin_manager: PluginManagerRuntimeProtocol,
    *,
    task_id: str,
    fencing_token: int,
) -> None:
    transaction = await plugin_manager.dependencies.databases.plugins.clone_transactions.get(
        task_id
    )
    if transaction is None or transaction.committed or transaction.phase == "rolled_back":
        return
    async with clone_operation_locks(
        plugin_manager,
        (transaction.target_plugin_name,),
        mutation_task_id=task_id,
        mutation_fencing_token=fencing_token,
    ):
        await rollback_clone_transaction(plugin_manager, task_id=task_id)
