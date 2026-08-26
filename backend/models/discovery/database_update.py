"""SoAI - Database mutation phase for discovered models [backend/models/discovery/database_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import VirtualModelConfig
from core.plugins.protocols import PluginManagerProtocol
from models.catalog_locking import enter_model_record_locks
from models.discovery.failure_deactivation import deactivate_models_for_failed_plugins
from models.discovery.provider_bounded_execution import PluginCheckUnchanged
from models.discovery.record_preparation import (
    index_model_candidates,
    model_fingerprint_records,
    prepare_model_upserts,
)
from models.discovery.removal_processing import (
    identify_and_log_removed_models,
    process_model_removals_in_db,
)
from models.discovery.virtual_model_reconciliation import (
    reconcile_virtual_models_for_removed_universal_ids,
)
from models.internal_protocols import ModelMutationEffectsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ModelDiscoveryUpdateDependencies",
    "update_discovered_models_in_db",
)

LOGGER_NAME = "SoAI.models.discovery.database_update"


@dataclass(frozen=True, slots=True)
class ModelDiscoveryUpdateDependencies:
    database_models: DatabaseModelsProtocol
    plugin_manager: PluginManagerProtocol
    metrics: MetricsManagerProtocol
    mutation_effects: ModelMutationEffectsProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]
    virtual_model_get: Callable[[str], Awaitable[VirtualModelConfig | None]]
    virtual_model_delete: Callable[[str], Awaitable[bool]]
    virtual_model_update: Callable[[str, JSONDict], Awaitable[VirtualModelConfig]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelDiscoveryUpdateDependencies",
            database_models=self.database_models,
            metrics=self.metrics,
            model_record_locks=self.model_record_locks,
            mutation_effects=self.mutation_effects,
            plugin_manager=self.plugin_manager,
            virtual_model_delete=self.virtual_model_delete,
            virtual_model_get=self.virtual_model_get,
            virtual_model_update=self.virtual_model_update,
        )


async def update_discovered_models_in_db(
    deps: ModelDiscoveryUpdateDependencies,
    discovered_data: dict[
        str,
        dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
    ],
    existing_models: dict[str, dict[str, JSONDict]],
    startup_discovery_complete: bool,
    last_model_upsert_fingerprint: str | None,
) -> str | None:
    indexed_candidates = index_model_candidates(discovered_data)
    initial_removed_universal_ids = identify_and_log_removed_models(
        discovered_data,
        existing_models,
        indexed_candidates["all_discovered_universal_ids_by_plugin"],
        startup_discovery_complete,
    )
    failed_plugin_names = {
        plugin_name
        for plugin_name, result in discovered_data.items()
        if isinstance(result, Exception) or result is None
    }
    lock_universal_ids = set(indexed_candidates["candidate_records_by_universal_id"])
    lock_universal_ids.update(initial_removed_universal_ids)
    for plugin_name in failed_plugin_names:
        for existing_record in existing_models.get(plugin_name, {}).values():
            universal_id = existing_record.get("universal_id")
            if isinstance(universal_id, str):
                lock_universal_ids.add(universal_id)
    if not lock_universal_ids and not failed_plugin_names:
        return last_model_upsert_fingerprint
    async with AsyncExitStack() as record_lock_stack:
        await enter_model_record_locks(
            record_lock_stack,
            deps.model_record_locks,
            lock_universal_ids,
        )
        authoritative_models = await deps.database_models.get_all_models_by_plugin()
        prepared_updates = prepare_model_upserts(indexed_candidates, authoritative_models)
        models_to_upsert = prepared_updates["models_to_upsert"]
        added_universal_ids = prepared_updates["added_universal_ids"]
        removed_universal_ids = identify_and_log_removed_models(
            discovered_data,
            authoritative_models,
            indexed_candidates["all_discovered_universal_ids_by_plugin"],
            startup_discovery_complete,
        )
        authoritative_affected_ids = set(removed_universal_ids)
        for plugin_name in failed_plugin_names:
            for authoritative_record in authoritative_models.get(plugin_name, {}).values():
                universal_id = authoritative_record.get("universal_id")
                if isinstance(universal_id, str):
                    authoritative_affected_ids.add(universal_id)
        unlocked_universal_ids = authoritative_affected_ids - lock_universal_ids
        if unlocked_universal_ids:
            raise StateError(
                "Model catalog changed while acquiring discovery reconciliation locks.",
                operation="models.discovery.update_discovered_models_in_db",
                details={"unlocked_universal_ids": sorted(unlocked_universal_ids)},
            )
        deactivated_universal_ids = await deactivate_models_for_failed_plugins(
            discovered_data,
            deps.database_models,
            deps.plugin_manager,
            deps.metrics,
        )
        if not (models_to_upsert or removed_universal_ids or deactivated_universal_ids):
            return last_model_upsert_fingerprint
        virtual_model_changed = await reconcile_virtual_models_for_removed_universal_ids(
            removed_universal_ids,
            deps.database_models,
            deps.virtual_model_get,
            deps.virtual_model_delete,
            deps.virtual_model_update,
        )
        if removed_universal_ids:
            await process_model_removals_in_db(
                removed_universal_ids,
                deps.database_models,
                deps.metrics,
            )
            await deps.mutation_effects.invalidate_parameter_cache_for_models(
                removed_universal_ids,
            )
        new_fingerprint = last_model_upsert_fingerprint
        if models_to_upsert:
            logger = get_logger(LOGGER_NAME)
            fingerprint = model_fingerprint_records(models_to_upsert)
            if fingerprint != last_model_upsert_fingerprint:
                logger.debug("Updating/inserting %s model records.", len(models_to_upsert))
            new_fingerprint = fingerprint
            deps.metrics.increment_counter(
                "model_manager",
                "models_updated",
                value=len(models_to_upsert),
            )
            await deps.database_models.upsert_models(models_to_upsert)
        if (
            models_to_upsert
            or removed_universal_ids
            or deactivated_universal_ids
            or virtual_model_changed
        ):
            await deps.mutation_effects.invalidate_all_resolution_cache()
            await deps.mutation_effects.publish_catalog_changed(
                added_universal_ids=added_universal_ids,
                removed_universal_ids=sorted(
                    set(removed_universal_ids + deactivated_universal_ids),
                ),
            )
        return new_fingerprint
