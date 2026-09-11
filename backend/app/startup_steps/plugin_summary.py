"""SoAI - Plugin startup availability summaries [backend/app/startup_steps/plugin_summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.state.state_names import resolve_plugin_runtime_state_name
from core.validation.strings import require_trimmed_json_text

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import StateAggregatorProtocol

__all__ = ("log_plugin_startup_summary",)

LOGGER_NAME = "SoAI.app.startup_steps.plugin_summary"


async def log_plugin_startup_summary(
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    records = await plugin_manager.dependencies.databases.plugins.get_all_listable_plugins()
    for record in records:
        plugin_name = require_trimmed_json_text(
            record.get("plugin_name"),
            error_message="Plugin startup summary requires a plugin name.",
        )
        state = resolve_plugin_runtime_state_name(
            await state_aggregator.get_plugin_status(plugin_name)
        )
        instance = await plugin_manager.get_plugin_instance(plugin_name)
        runtime = "loaded" if instance is not None else "not loaded"
        verification = (
            "runtime state available"
            if instance is not None
            else "deferred (catalog/recovery state)"
        )
        logger.info(
            "Plugin '%s': state=%s, runtime=%s, verification=%s.",
            plugin_name,
            state if state is not None else "unavailable",
            runtime,
            verification,
        )
