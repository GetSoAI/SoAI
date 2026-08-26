"""SoAI - Plugin listing and model browsing [backend/plugins/manager/listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import HardwareManagerProtocol
from core.logging.trace import get_logger
from core.models.remote_model_search_payloads import normalize_model_search_payload
from core.models.remote_model_search_types import RemoteModelSearchResult
from core.plugins.builtin_names import BUILTIN_PLUGIN_NAMES
from core.types.json import is_json_dict
from plugins.manager.backend_installation_drift import (
    compute_backend_installation_state_overrides,
    request_backend_installation_drift_scan,
)
from plugins.manager.backend_variant_counts import (
    merge_persisted_backend_variant_counts,
)
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.hydration import format_plugin_details
from plugins.variant_assessment import PluginVariantAssessor

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.types.protocols import HttpClientProtocol

__all__ = (
    "describe_model_variants",
    "get_plugin_stats",
    "list_plugins",
    "search_remote_models",
)

LOGGER_NAME = "SoAI.plugins.manager.listing"
OPERATION_PLUGINS_MANAGER_LISTING_BACKEND_INSTALLATION_DRIFT = (
    "plugins.manager.listing.backend_installation_drift"
)
OPERATION_PLUGINS_MANAGER_LISTING_GET_PLUGIN_STATS = "plugins.manager.listing.get_plugin_stats"
OPERATION_PLUGINS_MANAGER_LISTING_LIST_PLUGINS = "plugins.manager.listing.list_plugins"


async def list_plugins(self: PluginManagerRuntimeProtocol) -> list[JSONDict]:
    database_plugins = await self.dependencies.databases.plugins.get_all_listable_plugins()
    builtin_plugins = set(BUILTIN_PLUGIN_NAMES)
    plugin_names: list[str] = [
        plugin_name
        for plugin in database_plugins
        if isinstance((plugin_name := plugin.get("plugin_name")), str) and plugin_name
    ]
    plugin_stats = await get_plugin_stats(self, plugin_names)
    breaker_snapshot_map: dict[str, JSONDict] = {}
    lifecycle = self.orchestrator_lifecycle
    if lifecycle is not None:
        try:
            live_breaker_snapshots = (
                await lifecycle.circuit_breakers.get_all_circuit_breaker_snapshots()
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to fetch live circuit breaker snapshots during plugin listing (non-critical).",
                operation=OPERATION_PLUGINS_MANAGER_LISTING_LIST_PLUGINS,
                level="debug",
            )
            live_breaker_snapshots = {}
        for plugin_name, snapshot in live_breaker_snapshots.items():
            if isinstance(plugin_name, str) and plugin_name and isinstance(snapshot, dict):
                breaker_snapshot_map[plugin_name] = snapshot
    if len(breaker_snapshot_map) < len(plugin_names):
        breaker_snapshots = (
            await self.dependencies.databases.plugins.get_all_circuit_breaker_states()
        )
        for snapshot in breaker_snapshots:
            plugin_name = snapshot.get("plugin_name")
            if (
                isinstance(plugin_name, str)
                and plugin_name
                and plugin_name not in breaker_snapshot_map
            ):
                breaker_snapshot_map[plugin_name] = snapshot
    backend_installation_overrides: dict[str, str] = {}
    try:
        backend_installation_overrides = compute_backend_installation_state_overrides(
            self,
            database_plugins,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Backend installation drift detection failed during plugin listing (non-critical).",
            operation=OPERATION_PLUGINS_MANAGER_LISTING_BACKEND_INSTALLATION_DRIFT,
            level="debug",
        )
    if backend_installation_overrides:
        await request_backend_installation_drift_scan(
            self,
            reason="plugin_listing_backend_installation_drift",
        )
    merge_persisted_backend_variant_counts(
        self,
        database_plugins,
        plugin_stats,
        backend_installation_overrides,
    )
    plugin_details_list: list[JSONDict] = []
    for p_data in database_plugins:
        plugin_name_value = p_data.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        effective_p_data = p_data
        if plugin_name_value in backend_installation_overrides:
            effective_p_data = dict(p_data)
            effective_p_data["state"] = backend_installation_overrides[plugin_name_value]
        breaker_snapshot = breaker_snapshot_map.get(plugin_name_value)
        plugin_details_list.append(
            format_plugin_details(
                self,
                effective_p_data,
                instance=None,
                status_payload=None,
                plugin_stats=plugin_stats,
                builtin_plugins=builtin_plugins,
                breaker_snapshot=breaker_snapshot,
            ),
        )
    return sorted(
        plugin_details_list,
        key=lambda plugin_item: (
            not plugin_item["is_builtin"],
            str(plugin_item["display_name"]).lower(),
        ),
    )


async def get_plugin_stats(
    manager: PluginManagerRuntimeProtocol,
    plugin_names: list[str],
) -> dict[str, dict[str, int]]:
    stats = {name: {"model_count": 0, "provider_count": 0} for name in plugin_names}
    if not plugin_names:
        return stats
    try:
        batch = await manager.dependencies.databases.plugins.get_stats_for_plugins(plugin_names)
        for name in plugin_names:
            if name in batch:
                stats[name] = batch[name]
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            manager.logger,
            exception,
            message="Failed to fetch model/provider counts during plugin listing.",
            operation=OPERATION_PLUGINS_MANAGER_LISTING_GET_PLUGIN_STATS,
            level="warning",
        )
    return stats


async def search_remote_models(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    query: str,
    *,
    limit: int = 10,
) -> list[JSONDict]:
    await self.require_ready()
    self.require_online_mode("remote_model_search")
    if not (normalized_name := self.normalize_plugin_name(plugin_name)):
        raise ValidationError(f"Plugin '{plugin_name}' not found.")
    release_after_search = await self.get_plugin_instance(normalized_name) is None
    try:
        instance = await self.require_loaded_plugin(normalized_name, plugin_name, auto_load=True)
        if not supports_plugin_capability_from_instance(instance, "SUPPORTS_MODEL_DOWNLOAD"):
            raise ValidationError(f"Plugin '{plugin_name}' does not support model downloads.")
        if not supports_plugin_capability_from_instance(instance, "SUPPORTS_MODEL_SEARCH"):
            raise ValidationError(f"Plugin '{plugin_name}' does not support remote model search.")
        search_results = await instance.search_remote_models(query, limit=limit)
        normalized_items: list[RemoteModelSearchResult | JSONDict] = []
        for item in search_results:
            if isinstance(item, RemoteModelSearchResult) or is_json_dict(item):
                normalized_items.append(item)
        return normalize_model_search_payload(normalized_items)
    finally:
        if release_after_search:
            await uncancel_then_cleanup(self.release_discovery_plugin_instance(normalized_name))


async def describe_model_variants(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    model_id: str,
    *,
    include_speed_tests: bool = False,
    hw_manager: HardwareManagerProtocol | None = None,
    http_client: HttpClientProtocol | None = None,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    resolved_hw_manager = (
        hw_manager if hw_manager is not None else self.dependencies.infrastructure.hw_manager
    )
    resolved_http_client = (
        http_client if http_client is not None else self.dependencies.core.http_client
    )
    return await PluginVariantAssessor(logger).describe(
        self,
        plugin_name,
        model_id,
        include_speed_tests=include_speed_tests,
        hw_manager=resolved_hw_manager,
        database_plugins=self.dependencies.databases.plugins,
        database_hardware=self.dependencies.databases.hardware,
        http_client=resolved_http_client,
    )
