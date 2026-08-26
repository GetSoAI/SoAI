"""SoAI - Model removal identification and database processing [backend/models/discovery/removal_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from models.discovery.provider_bounded_execution import PluginCheckUnchanged

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "identify_and_log_removed_models",
    "process_model_removals_in_db",
)

LOGGER_NAME = "SoAI.models.discovery.removal_processing"


def identify_and_log_removed_models(
    discovered_data: dict[
        str,
        dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
    ],
    existing_models_by_plugin: dict[str, dict[str, JSONDict]],
    all_discovered_universal_ids_by_plugin: dict[str, set[str]],
    startup_discovery_complete: bool,
) -> list[str]:
    removed_universal_ids: list[str] = []
    if startup_discovery_complete and not all_discovered_universal_ids_by_plugin:
        return removed_universal_ids
    for plugin_name, models in discovered_data.items():
        if not isinstance(models, dict):
            continue
        if (
            not startup_discovery_complete
            and not models
            and existing_models_by_plugin.get(plugin_name)
        ):
            continue
        removed_universal_ids.extend(
            {
                universal_id
                for model_record in existing_models_by_plugin.get(plugin_name, {}).values()
                if isinstance((universal_id := model_record.get("universal_id")), str)
            }
            - all_discovered_universal_ids_by_plugin.get(plugin_name, set()),
        )
    if not startup_discovery_complete:
        return []
    return removed_universal_ids


async def process_model_removals_in_db(
    removed_universal_ids: list[str],
    database_models: DatabaseModelsProtocol,
    metrics: MetricsManagerProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    ordered_universal_ids = sorted(set(removed_universal_ids))
    logger.debug(
        "Removing %s stale model records from the database.",
        len(ordered_universal_ids),
    )
    metrics.increment_counter(
        "model_manager",
        "models_removed",
        value=len(ordered_universal_ids),
    )
    if not ordered_universal_ids:
        return
    deleted_count = await database_models.delete_models_by_ids(ordered_universal_ids)
    if deleted_count != len(ordered_universal_ids):
        remaining_models = await database_models.get_models_info(ordered_universal_ids)
        if not remaining_models:
            return
        raise StateError(
            "Failed to delete all stale models from database.",
            operation="models.discovery.process_model_removals_in_db",
            details={
                "requested_count": len(ordered_universal_ids),
                "deleted_count": deleted_count,
                "remaining_universal_ids": sorted(remaining_models),
            },
        )
