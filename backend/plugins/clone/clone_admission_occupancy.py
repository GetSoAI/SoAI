"""SoAI - Clone pre-admission filesystem occupancy [backend/plugins/clone/clone_admission_occupancy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX, PLUGIN_FILE_SUFFIX
from core.plugins.portable_identifiers import is_portable_plugin_identifier
from core.plugins.runtime_services import PluginPathResolver
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("snapshot_clone_target_occupancy",)


def _plugin_artifact_names(plugin_directory: str) -> set[str]:
    occupied: set[str] = set()
    with os.scandir(plugin_directory) as entries:
        for entry in entries:
            candidate: str | None = None
            if entry.name.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
                candidate = entry.name[: -len(PLUGIN_CONFIG_FILE_SUFFIX)]
            elif entry.name.endswith(PLUGIN_FILE_SUFFIX):
                candidate = entry.name[: -len(PLUGIN_FILE_SUFFIX)]
            if candidate is not None and is_portable_plugin_identifier(candidate):
                occupied.add(candidate)
    return occupied


def _models_artifact_names(source_models_path: str) -> set[str]:
    if not os.path.lexists(source_models_path):
        return set()
    models_parent = os.path.dirname(source_models_path)
    if not models_parent:
        return set()
    occupied: set[str] = set()
    with os.scandir(models_parent) as entries:
        for entry in entries:
            if is_portable_plugin_identifier(entry.name):
                occupied.add(entry.name)
    return occupied


def _portable_child_names(directory: str) -> set[str]:
    try:
        with os.scandir(directory) as entries:
            return {entry.name for entry in entries if is_portable_plugin_identifier(entry.name)}
    except FileNotFoundError:
        return set()


def _validation_cache_names(temp_directory: str) -> set[str]:
    validation_directory = os.path.join(temp_directory, "plugin_validation_cache")
    try:
        with os.scandir(validation_directory) as entries:
            return {
                entry.name.removesuffix(".sha256")
                for entry in entries
                if entry.name.endswith(".sha256")
                and is_portable_plugin_identifier(entry.name.removesuffix(".sha256"))
            }
    except FileNotFoundError:
        return set()


def _runtime_artifact_names(
    backends_directory: str,
    venvs_directory: str,
    temp_directory: str,
) -> set[str]:
    occupied = _portable_child_names(backends_directory)
    occupied.update(_portable_child_names(venvs_directory))
    occupied.update(_portable_child_names(os.path.join(temp_directory, "plugin_packages")))
    occupied.update(_validation_cache_names(temp_directory))
    return occupied


async def _resolve_source_models_path(
    manager: PluginManagerRuntimeProtocol,
    source_plugin_name: str,
    source_instance: PluginInstanceProtocol | None,
) -> str:
    if source_instance is not None:
        return source_instance.get_models_directory()
    loaded_config = await manager.dependencies.infrastructure.config_manager.load_config(
        source_plugin_name,
        force_reload=True,
    )
    plugin_config = (
        coerce_json_dict(normalize_for_json(loaded_config)) if loaded_config is not None else {}
    )
    if plugin_config is None:
        raise StateError("Source plugin configuration is invalid for clone admission.")
    return PluginPathResolver(
        source_plugin_name,
        manager.dependencies.core.config,
        manager.dependencies.core.files,
        plugin_config,
    ).models_directory()


async def snapshot_clone_target_occupancy(
    manager: PluginManagerRuntimeProtocol,
    *,
    source_plugin_name: str,
    source_instance: PluginInstanceProtocol | None,
    clone_models: bool,
) -> tuple[str, ...]:
    occupied = await asyncio.to_thread(
        _plugin_artifact_names,
        manager.paths.plugin_directory,
    )
    occupied.update(
        await asyncio.to_thread(
            _runtime_artifact_names,
            manager.paths.backends_directory,
            manager.paths.plugin_venvs_root,
            manager.paths.temp_directory,
        )
    )
    if clone_models:
        source_models_path = await _resolve_source_models_path(
            manager,
            source_plugin_name,
            source_instance,
        )
        occupied.update(await asyncio.to_thread(_models_artifact_names, source_models_path))
    return tuple(sorted(occupied))
