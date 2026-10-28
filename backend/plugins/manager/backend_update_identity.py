"""SoAI - Audited package and effective configuration identity [backend/plugins/manager/backend_update_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from core.errors.exceptions import StateError
from core.plugins.backend_update_records import BackendUpdateIdentity
from core.serialization.json import normalize_for_json, serialize_json_compact_stable
from core.state.state_names import PLUGIN_STATE_NOT_DETECTED
from core.types.json import JSONDict
from core.validation.booleans import parse_bool
from plugins.artifact_paths import get_plugin_file_hash
from plugins.manager.compatibility import ensure_record_is_compatible
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("backend_configuration_digest", "capture_backend_update_identity")


def backend_configuration_digest(configuration: JSONDict) -> str:
    return hashlib.sha256(serialize_json_compact_stable(configuration).encode("utf-8")).hexdigest()


async def capture_backend_update_identity(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    require_loaded_hash: bool,
) -> BackendUpdateIdentity:
    record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if record is None or record.get("state") == PLUGIN_STATE_NOT_DETECTED:
        raise StateError("Backend update plugin is no longer present.")
    ensure_record_is_compatible(manager, plugin_name, record)
    package_hash = await get_plugin_file_hash(manager, plugin_name)
    if package_hash is None or package_hash != record.get("file_hash"):
        raise StateError("Backend update package identity changed.")
    if require_loaded_hash:
        async with manager.state.locks.load_lock:
            surface = manager.state.catalog.loaded_plugin_surfaces.get(plugin_name)
            if surface is None or surface[1] != package_hash:
                raise StateError("Backend update worker does not match its audited package.")
    configuration_hash = None
    if parse_bool(record.get("has_configuration"), default=False):
        configuration = normalize_for_json(
            await manager.dependencies.infrastructure.config_manager.load_config(
                plugin_name, force_reload=True
            )
        )
        if not isinstance(configuration, dict):
            raise StateError("Backend update configuration is unavailable.")
        configuration_hash = backend_configuration_digest(configuration)
    return BackendUpdateIdentity(
        plugin_name,
        package_hash,
        configuration_hash,
        await manager.snapshot_backend_variant_selection(plugin_name),
    )
