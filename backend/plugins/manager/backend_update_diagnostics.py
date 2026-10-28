"""SoAI - Explicit sequential backend update diagnostics [backend/plugins/manager/backend_update_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.backend_update_results import backend_update_error
from core.runtime.network_policy import require_online_mode
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.manager.backend_update_checks import check_backend_update
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("check_for_backend_updates",)

OPERATION = "plugins.manager.backend_update_diagnostics"


def _is_backend_update_check_candidate(
    manager: PluginManagerRuntimeProtocol, plugin: JSONDict
) -> bool:
    for key in ("installed", "is_available"):
        if not coerce_bool_with_recovery(
            plugin, key, logger=manager.logger, operation=OPERATION, default=False
        ):
            return False
    capabilities = plugin.get("capabilities")
    return isinstance(capabilities, dict) and coerce_bool_with_recovery(
        capabilities,
        "supports_backend_installation",
        logger=manager.logger,
        operation=OPERATION,
        default=False,
    )


async def check_for_backend_updates(manager: PluginManagerRuntimeProtocol) -> dict[str, JSONDict]:
    manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    require_online_mode(
        manager.dependencies.infrastructure.runtime_flags, source="plugin backend update check"
    )
    updates: dict[str, JSONDict] = {}
    for plugin in await manager.list_plugins():
        plugin_name = plugin.get("name")
        if not isinstance(plugin_name, str) or not plugin_name:
            continue
        if _is_backend_update_check_candidate(manager, plugin):
            updates[plugin_name] = await check_backend_update(manager, plugin_name)
        else:
            updates[plugin_name] = backend_update_error(
                "not_implemented", "Update check not supported."
            ).payload
    return updates
