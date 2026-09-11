"""SoAI - Plugin manager public operations [backend/plugins/manager/public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.hardware.protocols import HardwareManagerProtocol
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.plugins.protocols_manager_dependencies import PluginManagerDependenciesProtocol
from core.state.compatibility import CompatibilityInfo
from core.state.state_transition_sets import ACTIVE_RESOURCE_STATES
from core.types.json import JSONDict, JSONValue
from core.types.protocols import HttpClientProtocol
from core.validation.booleans import parse_bool
from core.validation.strings import coerce_optional_trimmed_str, require_trimmed_text
from plugins.clone.clone_admission_occupancy import snapshot_clone_target_occupancy
from plugins.loader.override import set_incompatibility_override
from plugins.manager.backend_variants import (
    get_backend_variants,
    save_backend_variant_selection,
    snapshot_backend_variant_selection,
)
from plugins.manager.capabilities import ensure_plugin_capability
from plugins.manager.compatibility import (
    ensure_plugin_compatible,
    ensure_system_capabilities,
)
from plugins.manager.configuration import (
    get_plugin_configuration,
    refresh_plugin_runtime_configuration,
    set_plugin_configuration,
)
from plugins.manager.display_names import (
    resolve_plugin_display_name,
    resolve_plugin_display_names,
)
from plugins.manager.instance_loading import (
    reload_plugin_instance,
    require_loaded_plugin,
)
from plugins.manager.instances import clear_loaded_plugin_state, get_plugin_instance
from plugins.manager.listing import (
    describe_model_variants,
    list_plugins,
    search_remote_models,
)
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.manager.name_normalization import (
    call_with_optional_plugin_name,
    call_with_required_plugin_name,
    normalize_optional_plugin_name,
    normalize_or_original,
    normalize_required_plugin_name,
)
from plugins.manager.transfer_operations import PluginManagerTransferOperations
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("PluginManagerOperations",)


class PluginManagerOperations(PluginManagerTransferOperations):
    if not TYPE_CHECKING:
        dependencies: PluginManagerDependenciesProtocol

    async def list_plugins(self: PluginManagerRuntimeProtocol) -> list[JSONDict]:
        return await list_plugins(self)

    async def describe_model_variants(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        model_id: str,
        *,
        include_speed_tests: bool = False,
        hw_manager: HardwareManagerProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> list[JSONDict]:
        normalized_model_id = require_trimmed_text(model_id, "model_id is required.")
        return await describe_model_variants(
            self,
            plugin_name,
            normalized_model_id,
            include_speed_tests=include_speed_tests,
            hw_manager=hw_manager,
            http_client=http_client,
        )

    async def get_plugin_configuration(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> JSONDict:
        return await call_with_required_plugin_name(self, plugin_name, get_plugin_configuration)

    async def set_plugin_configuration(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        config_data: JSONDict,
        *,
        apply_runtime: bool = True,
    ) -> bool:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        return await set_plugin_configuration(
            self,
            normalized_plugin_name,
            config_data,
            apply_runtime=apply_runtime,
        )

    async def refresh_plugin_runtime_configuration(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        *,
        auto_load: bool = True,
    ) -> JSONDict:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        return await refresh_plugin_runtime_configuration(
            self,
            normalized_plugin_name,
            auto_load=auto_load,
        )

    async def get_backend_variants(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> JSONDict:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        return await get_backend_variants(self, normalized_plugin_name)

    async def save_backend_variant_selection(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        variant_id: JSONValue,
    ) -> JSONDict:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        return await save_backend_variant_selection(self, normalized_plugin_name, variant_id)

    async def snapshot_backend_variant_selection(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        requested_variant_id: JSONValue = None,
        *,
        has_requested_variant_id: bool = False,
    ) -> str:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        return await snapshot_backend_variant_selection(
            self,
            normalized_plugin_name,
            requested_variant_id,
            has_requested_variant_id=has_requested_variant_id,
        )

    async def get_plugin_display_name(self: PluginManagerRuntimeProtocol, plugin_name: str) -> str:
        self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
        normalized_plugin_name = normalize_optional_plugin_name(self, plugin_name)
        if normalized_plugin_name is None:
            return "Unknown"
        return await resolve_plugin_display_name(self, normalized_plugin_name)

    async def get_plugin_display_names(
        self: PluginManagerRuntimeProtocol,
        plugin_names: Iterable[str],
    ) -> dict[str, str]:
        self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
        canonical_plugin_names = [
            normalized_name
            for plugin_name in plugin_names
            if (normalized_name := normalize_optional_plugin_name(self, plugin_name)) is not None
        ]
        return await resolve_plugin_display_names(self, canonical_plugin_names)

    async def get_plugin_instance(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> PluginInstanceProtocol | None:
        return await call_with_optional_plugin_name(self, plugin_name, None, get_plugin_instance)

    async def snapshot_clone_target_occupancy(
        self: PluginManagerRuntimeProtocol,
        source_plugin_name: str,
        source_instance: PluginInstanceProtocol | None,
        clone_models: bool,
    ) -> tuple[str, ...]:
        return await snapshot_clone_target_occupancy(
            self,
            source_plugin_name=source_plugin_name,
            source_instance=source_instance,
            clone_models=clone_models,
        )

    async def require_loaded_plugin(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        display_name: str | None = None,
        auto_load: bool = False,
        *,
        already_serialized: bool = False,
    ) -> PluginInstanceProtocol:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        resolved_display_name = (
            display_name.strip() if isinstance(display_name, str) else display_name
        )
        return await require_loaded_plugin(
            self,
            normalized_plugin_name,
            resolved_display_name,
            auto_load=auto_load,
            already_serialized=already_serialized,
        )

    async def ensure_system_capabilities(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        action_description: str,
        action_key: str | None = None,
    ) -> JSONDict:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        resolved_action_description = normalize_or_original(action_description)
        return await ensure_system_capabilities(
            self,
            normalized_plugin_name,
            resolved_action_description,
            action_key=action_key,
        )

    async def search_remote_models(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[JSONDict]:
        normalized_query = coerce_optional_trimmed_str(query)
        if normalized_query is None:
            return []
        return await search_remote_models(self, plugin_name, normalized_query, limit=limit)

    async def reload_plugin_instance(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
        await call_with_required_plugin_name(self, plugin_name, reload_plugin_instance)

    async def release_discovery_plugin_instance(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> None:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        plugin_record = await self.dependencies.databases.plugins.get_plugin_by_name(
            normalized_plugin_name,
        )
        if plugin_record is not None and parse_bool(
            plugin_record.get("persistent"),
            default=False,
        ):
            return
        current_state = await self.dependencies.infrastructure.state_aggregator.get_plugin_status(
            normalized_plugin_name,
        )
        if current_state in ACTIVE_RESOURCE_STATES:
            return
        await clear_loaded_plugin_state(self, normalized_plugin_name)
        await self.dependencies.databases.plugins.update_plugin_runtime_loaded(
            normalized_plugin_name,
            False,
        )

    async def ensure_plugin_compatible(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> None:
        await call_with_required_plugin_name(self, plugin_name, ensure_plugin_compatible)

    async def set_incompatibility_override(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        override: bool,
    ) -> CompatibilityInfo:
        normalized_plugin_name = normalize_or_original(plugin_name)
        async with serialized_plugin_load_scope(self, normalized_plugin_name):
            return await run_idempotent_current_task_operation(
                lambda: set_incompatibility_override(
                    self,
                    normalized_plugin_name,
                    override,
                )
            )

    async def ensure_plugin_capability(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        capability_name: str,
        action_description: str,
    ) -> None:
        normalized_plugin_name = normalize_required_plugin_name(self, plugin_name)
        resolved_action_description = normalize_or_original(action_description)
        await ensure_plugin_capability(
            self,
            normalized_plugin_name,
            capability_name,
            resolved_action_description,
        )
