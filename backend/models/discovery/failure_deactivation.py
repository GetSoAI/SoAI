"""SoAI - Model deactivation for failed discovery providers [backend/models/discovery/failure_deactivation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.plugins.protocols import PluginManagerProtocol
from models.discovery.provider_bounded_execution import PluginCheckUnchanged

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("deactivate_models_for_failed_plugins",)

LOGGER_NAME = "SoAI.models.discovery.failure_deactivation"
OPERATION = "model_discovery.deactivate_models_for_failed_plugins"


async def deactivate_models_for_failed_plugins(
    discovered_data: dict[
        str,
        dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
    ],
    database_models: DatabaseModelsProtocol,
    plugin_manager: PluginManagerProtocol,
    metrics: MetricsManagerProtocol,
) -> list[str]:
    logger = get_logger(LOGGER_NAME)
    deactivated_universal_ids: list[str] = []
    for plugin_name, discovery_result in discovered_data.items():
        if isinstance(discovery_result, Exception) or discovery_result is None:
            display_name = await plugin_manager.get_plugin_display_name(plugin_name)
            if isinstance(discovery_result, Exception):
                log_exception(
                    logger,
                    discovery_result,
                    message=f"Discovery for '{display_name}' failed. Deactivating associated models.",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                )
            else:
                logger.warning(
                    "Discovery for '%s' returned None. Deactivating associated models.",
                    display_name,
                )
            metrics.increment_counter("model_manager", "discoveries_failed", plugin_name)
            affected_count, affected_universal_ids = (
                await database_models.set_model_status_for_plugin(
                    plugin_name,
                    "inactive_plugin_error",
                )
            )
            if affected_count > 0:
                logger.debug(
                    "Deactivated %s models for failed plugin '%s'.",
                    affected_count,
                    display_name,
                )
                deactivated_universal_ids.extend(affected_universal_ids)
    return deactivated_universal_ids
