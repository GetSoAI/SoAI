"""SoAI - Database-only model purge service for plugin removal workflows [backend/models/actions/purge_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import EventPublicationReceipt, await_publication_receipt
from core.events.protocols import EventBusProtocol
from core.events.types_models_model_events import ModelDatabaseChangeEvent
from core.logging.trace import get_logger
from core.models.protocols_database import DatabaseModelsProtocol
from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
from models.catalog_locking import enter_model_record_locks

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ModelDatabasePurgeService",
    "ModelDatabasePurgeServiceDependencies",
)

LOGGER_NAME = "SoAI.models.actions.purge_records"
OPERATION_MODEL_PURGE_DATABASE_PURGE_GET_ALL_MODELS_BY_PLUGIN = (
    "model_purge.database_purge.get_all_models_by_plugin"
)
OPERATION_MODEL_PURGE_DATABASE_PURGE_PURGE_MODELS_FOR_PLUGIN = (
    "model_purge.database_purge.purge_models_for_plugin"
)


@dataclass(frozen=True, slots=True)
class ModelDatabasePurgeServiceDependencies:
    database_models: DatabaseModelsProtocol
    event_bus: EventBusProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelDatabasePurgeServiceDependencies",
            database_models=self.database_models,
            event_bus=self.event_bus,
            model_record_locks=self.model_record_locks,
        )


class ModelDatabasePurgeService:
    def __init__(self, deps: ModelDatabasePurgeServiceDependencies) -> None:
        self._deps = deps

    async def purge_models_for_plugin(
        self,
        plugin_name: str,
        plugin_lifecycle: PluginLifecycleProtocol,
    ) -> bool:
        logger = get_logger(LOGGER_NAME)
        if not plugin_name:
            raise ValidationError("plugin_name must be provided.")
        async with AsyncExitStack() as lock_stack:
            if not plugin_lifecycle.is_plugin_lock_owned_by_current_task(plugin_name):
                await lock_stack.enter_async_context(
                    plugin_lifecycle.plugin_lock_scope(plugin_name),
                )
            try:
                baseline_models = await self._deps.database_models.get_all_models_by_plugin()
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to retrieve models for purge",
                    operation=OPERATION_MODEL_PURGE_DATABASE_PURGE_GET_ALL_MODELS_BY_PLUGIN,
                    details={"plugin_name": plugin_name},
                )
                raise
            baseline_universal_ids = _model_universal_ids(baseline_models, plugin_name)
            await enter_model_record_locks(
                lock_stack,
                self._deps.model_record_locks,
                baseline_universal_ids,
            )
            authoritative_models = await self._deps.database_models.get_all_models_by_plugin()
            removed_universal_ids = _model_universal_ids(authoritative_models, plugin_name)
            unlocked_ids = set(removed_universal_ids) - set(baseline_universal_ids)
            if unlocked_ids:
                raise StateError(
                    "Plugin model catalog changed while acquiring purge locks.",
                    operation=OPERATION_MODEL_PURGE_DATABASE_PURGE_PURGE_MODELS_FOR_PLUGIN,
                    details={
                        "plugin_name": plugin_name,
                        "unlocked_universal_ids": sorted(unlocked_ids),
                    },
                )
            try:
                did_purge = await self._deps.database_models.purge_models_for_plugin(plugin_name)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to purge model records from database",
                    operation=OPERATION_MODEL_PURGE_DATABASE_PURGE_PURGE_MODELS_FOR_PLUGIN,
                    details={"plugin_name": plugin_name},
                )
                raise
            remaining_models = await self._deps.database_models.get_all_models_by_plugin()
            remaining_universal_ids = _model_universal_ids(remaining_models, plugin_name)
            if remaining_universal_ids:
                raise StateError(
                    "Failed to purge all plugin model records.",
                    operation=OPERATION_MODEL_PURGE_DATABASE_PURGE_PURGE_MODELS_FOR_PLUGIN,
                    details={
                        "plugin_name": plugin_name,
                        "remaining_universal_ids": remaining_universal_ids,
                    },
                )
            if did_purge and removed_universal_ids:
                receipt = EventPublicationReceipt.create(
                    event_type=ModelDatabaseChangeEvent.__name__,
                    operation=OPERATION_MODEL_PURGE_DATABASE_PURGE_PURGE_MODELS_FOR_PLUGIN,
                )
                await self._deps.event_bus.publish(
                    ModelDatabaseChangeEvent(removed_universal_ids=removed_universal_ids),
                    wait_for_completion=receipt.completion_signal,
                )
                await await_publication_receipt(receipt)
            return bool(did_purge)


def _model_universal_ids(
    models_by_plugin: dict[str, dict[str, JSONDict]],
    plugin_name: str,
) -> list[str]:
    return sorted(
        universal_id
        for model_record in models_by_plugin.get(plugin_name, {}).values()
        if isinstance((universal_id := model_record.get("universal_id")), str) and universal_id
    )
