"""SoAI - Plugin backend variant manager operations [backend/plugins/manager/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation_cleanup import cancellation_cleanup, uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_variant_status import read_installed_backend_variant_id
from core.plugins.backend_variants import (
    AUTO_BACKEND_VARIANT_ID,
    count_available_backend_variant_options,
    is_backend_variant_available,
    require_backend_variant_id,
    require_known_backend_variant_id,
)
from core.plugins.persistent_runtime_truth import get_plugin_status_payload
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_REMOVING_BACKEND,
)
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.types.json import JSONDict, JSONValue
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_variant_compatibility import load_backend_variant_compatibility
from plugins.manager.backend_variant_counts import persist_backend_variant_count
from plugins.manager.backend_variant_option_loading import load_backend_variant_options
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "get_backend_variants",
    "save_backend_variant_selection",
    "snapshot_backend_variant_selection",
)

INSTALLED_VARIANT_RESOLUTION_RESOLVED = "resolved"
INSTALLED_VARIANT_RESOLUTION_NOT_INSTALLED = "not_installed"
INSTALLED_VARIANT_RESOLUTION_UNAVAILABLE = "unavailable"
INSTALLED_VARIANT_RESOLUTION_NOT_REQUESTED = "not_requested"
OPERATION_RESOLVE_INSTALLED_BACKEND_VARIANT = "plugins.resolve_installed_backend_variant"


async def snapshot_backend_variant_selection(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    requested_variant_id: JSONValue = None,
    *,
    has_requested_variant_id: bool = False,
) -> str:
    if has_requested_variant_id:
        variant_id = require_backend_variant_id(requested_variant_id)
    else:
        raw_variant_id = await manager.dependencies.databases.plugins.get_backend_variant_id(
            plugin_name,
        )
        variant_id = require_backend_variant_id(raw_variant_id or AUTO_BACKEND_VARIANT_ID)
    options = await load_backend_variant_options(manager, plugin_name)
    if not has_requested_variant_id and not is_backend_variant_available(variant_id, options):
        return AUTO_BACKEND_VARIANT_ID
    return require_known_backend_variant_id(variant_id, options)


async def resolve_installed_backend_variant(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    durable_state: str | None = None,
) -> JSONDict:
    unavailable: JSONDict = {
        "installed_variant_id": None,
        "installed_variant_resolution": INSTALLED_VARIANT_RESOLUTION_UNAVAILABLE,
    }
    if durable_state in (
        PLUGIN_STATE_BACKEND_INSTALLING,
        PLUGIN_STATE_BACKEND_UPDATING,
        PLUGIN_STATE_REMOVING_BACKEND,
        PLUGIN_STATE_DELETING,
    ):
        return unavailable
    async with manager.dependencies.infrastructure.lifecycle.bounded_plugin_lock_scope(
        plugin_name, timeout_seconds=RESPONSIVE_TIMEOUT_SEC
    ) as admission:
        if not admission.acquired:
            return unavailable
        instance = await manager.get_plugin_instance(plugin_name)
        if instance is None and durable_state == PLUGIN_STATE_BACKEND_NOT_INSTALLED:
            return {
                "installed_variant_id": None,
                "installed_variant_resolution": INSTALLED_VARIANT_RESOLUTION_NOT_INSTALLED,
            }
        release_after_discovery = instance is None
        if instance is None:
            try:
                instance = await manager.require_loaded_plugin(
                    plugin_name,
                    auto_load=True,
                    already_serialized=True,
                )
            except StateError:
                return unavailable
        try:
            try:
                status_payload = await get_plugin_status_payload(
                    instance,
                    operation=OPERATION_RESOLVE_INSTALLED_BACKEND_VARIANT,
                    logger=manager.logger,
                    raise_on_error=True,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    manager.logger,
                    exception,
                    message=(
                        f"Installed backend variant discovery is unavailable for "
                        f"plugin '{plugin_name}'."
                    ),
                    operation=OPERATION_RESOLVE_INSTALLED_BACKEND_VARIANT,
                    details={"plugin": plugin_name},
                )
                return unavailable
            return {
                "installed_variant_id": read_installed_backend_variant_id(status_payload),
                "installed_variant_resolution": INSTALLED_VARIANT_RESOLUTION_RESOLVED,
            }
        finally:
            if release_after_discovery:
                await uncancel_then_cleanup(
                    manager.release_discovery_plugin_instance(plugin_name),
                )


async def get_backend_variants(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    discover_installed_variant: bool = True,
) -> JSONDict:
    selected = await manager.dependencies.databases.plugins.get_backend_variant_id(plugin_name)
    selected_variant_id = require_backend_variant_id(selected or AUTO_BACKEND_VARIANT_ID)
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    state_value = plugin_record.get("state") if plugin_record is not None else None
    durable_state = state_value if isinstance(state_value, str) else None
    options = await load_backend_variant_options(manager, plugin_name)
    if not is_backend_variant_available(selected_variant_id, options):
        selected_variant_id = AUTO_BACKEND_VARIANT_ID
    installed_variant_resolution: JSONDict
    if discover_installed_variant:
        installed_variant_resolution = await resolve_installed_backend_variant(
            manager,
            plugin_name,
            durable_state,
        )
    else:
        installed_variant_resolution = {
            "installed_variant_id": None,
            "installed_variant_resolution": INSTALLED_VARIANT_RESOLUTION_NOT_REQUESTED,
        }
    result: JSONDict = {
        "selected_variant_id": selected_variant_id,
        "options": await load_backend_variant_compatibility(manager, plugin_name, options),
        "available_count": count_available_backend_variant_options(options),
        **installed_variant_resolution,
    }
    if durable_state is not None:
        await persist_backend_variant_count(manager, plugin_name, durable_state, options)
    return result


async def save_backend_variant_selection(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    variant_id: JSONValue,
) -> JSONDict:
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    state_value = plugin_record.get("state") if plugin_record is not None else None
    durable_state = state_value if isinstance(state_value, str) else None
    options = await load_backend_variant_options(manager, plugin_name)
    selected_variant_id = require_known_backend_variant_id(variant_id, options)
    installed_variant_resolution = await resolve_installed_backend_variant(
        manager,
        plugin_name,
        durable_state,
    )
    if durable_state is not None:
        await persist_backend_variant_count(manager, plugin_name, durable_state, options)
    async with plugin_lifecycle_advisory_lock(manager, plugin_name):
        async with serialized_plugin_load_scope(manager, plugin_name):
            options = await load_backend_variant_options(manager, plugin_name)
            selected_variant_id = require_known_backend_variant_id(variant_id, options)
            try:
                await cancellation_cleanup(
                    manager.dependencies.databases.plugins.set_backend_variant_id(
                        plugin_name, selected_variant_id
                    )
                )
            finally:
                manager.state.catalog.backend_update_publication_pending = True
                manager.state.catalog.backend_update_wake.set()
    return {
        "selected_variant_id": selected_variant_id,
        "options": await load_backend_variant_compatibility(manager, plugin_name, options),
        "available_count": count_available_backend_variant_options(options),
        **installed_variant_resolution,
    }
