"""SoAI - Plugin atomic registration and persistence [backend/plugins/loader/loading_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.compatibility import CompatibilityInfo
from core.state.state_names import ORCH_STATE_DISABLED
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "PluginLoadRegistration",
    "register_loaded_plugin",
)

LOGGER_NAME = "SoAI.plugins.loader.loading_registration"


@dataclass(frozen=True, slots=True)
class PluginLoadRegistration:
    plugin_name: str
    force_reload: bool
    plugin_class_name: str | None
    compatibility: CompatibilityInfo | None
    existing_record: JSONDict | None
    plugin_data: JSONDict
    file_hash: str
    final_instance: PluginInstanceProtocol
    initial_state: PluginRuntimeStateName
    reason: str
    persisted_state: str | None


async def register_loaded_plugin(
    manager: PluginManagerRuntimeProtocol,
    registration: PluginLoadRegistration,
) -> tuple[PluginInstanceProtocol, PluginRuntimeStateName, str]:
    logger = get_logger(LOGGER_NAME)
    plugin_name = registration.plugin_name
    final_instance = registration.final_instance
    initial_state = registration.initial_state
    reason = registration.reason
    async with manager.state.locks.load_lock:
        if plugin_name in manager.state.catalog.loaded_plugin_instances and (
            not registration.force_reload
        ):
            logger.info(
                "Plugin '%s' was loaded by another task concurrently. Aborting this load.",
                plugin_name,
            )
            concurrent_instance = manager.state.catalog.loaded_plugin_instances.get(plugin_name)
            if concurrent_instance is None:
                raise StateError(
                    f"Plugin '{plugin_name}' was marked as loaded without an instance.",
                )
            return (concurrent_instance, initial_state, reason)
        user_enabled_once = coerce_bool_with_recovery(
            registration.existing_record or {},
            "user_enabled_once",
            logger=logger,
            operation="plugins.loader.loading.coerce_user_enabled_once",
            default=False,
        )
        compatibility_info = registration.compatibility
        hardware_blocked = bool(
            compatibility_info
            and compatibility_info.reason in manager.policy.hardware_incompatible_reasons
            and (not compatibility_info.is_overridden),
        )
        if hardware_blocked and (not user_enabled_once) and compatibility_info:
            initial_state, reason = (
                ORCH_STATE_DISABLED,
                compatibility_info.message or "Plugin disabled due to unmet system capabilities.",
            )
        if (
            compatibility_info
            and compatibility_info.reason
            and (not compatibility_info.is_overridden)
            and (not hardware_blocked)
        ):
            raise PluginIncompatibleError(
                plugin_name,
                compatibility_info,
                plugin_class=None,
                plugin_class_name=registration.plugin_class_name,
            )
        await manager.dependencies.databases.plugins.add_or_update_plugin(
            registration.plugin_data,
            state=registration.persisted_state,
            incompatibility=(
                compatibility_info if compatibility_info and compatibility_info.reason else None
            ),
            override=(compatibility_info.is_overridden if compatibility_info else False),
        )
        manager.state.catalog.loaded_plugin_surfaces[plugin_name] = (
            registration.plugin_data,
            registration.file_hash,
        )
        manager.state.catalog.loaded_plugin_instances[plugin_name] = final_instance
    return (final_instance, initial_state, reason)
