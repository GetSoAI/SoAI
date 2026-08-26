"""SoAI - Base plugin surface methods [backend/core/plugins/base_plugin_surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import io
import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.config.runtime_config import ConfigError
from core.errors.exceptions import StateError
from core.plugins.protocols_runtime import (
    DefaultConfigurationProviderProtocol,
    PluginSurfaceProtocol,
)
from core.plugins.runtime_support import open_log_file

if TYPE_CHECKING:
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict

__all__ = (
    "get_default_configuration_template",
    "get_default_log_path",
    "get_models_directory",
    "open_log_file_for_command",
    "supports_modality",
)


def get_models_directory(plugin: PluginSurfaceProtocol) -> str:
    plugin_config = plugin.plugin_config
    files = plugin.files
    path_override = plugin_config.get("MODELS_PATH_OVERRIDE")
    if isinstance(path_override, os.PathLike) or (
        isinstance(path_override, str) and path_override.strip()
    ):
        return files.resolve_path(path_override)
    config = plugin.config
    plugin_name = plugin.plugin_name
    if not isinstance(plugin_name, str) or not plugin_name:
        raise StateError("Plugin runtime missing plugin_name.")
    models_base = config.require_str("MODELS.MANAGER.PATHS.MODELS")
    return files.resolve_path(os.path.join(models_base, plugin_name))


def supports_modality(plugin: PluginSurfaceProtocol, modality: str) -> bool:
    if not modality:
        return False
    supported_modalities = plugin.SUPPORTED_MODALITIES
    lowered = modality.lower()
    return any(lowered == str(item).lower() for item in supported_modalities)


def get_default_log_path(plugin: PluginSurfaceProtocol) -> str:
    config = plugin.config
    files = plugin.files
    plugin_name = plugin.plugin_name
    if not isinstance(plugin_name, str) or not plugin_name:
        raise StateError("Plugin runtime missing plugin_name.")
    plugin_logs_path = config.get_str("PLUGINS.PATHS.PLUGIN_LOGS")
    if not isinstance(plugin_logs_path, str) or not plugin_logs_path.strip():
        raise StateError("PLUGINS.PATHS.PLUGIN_LOGS must be a non-empty string.")
    return files.resolve_path(f"{plugin_logs_path}/{plugin_name}.log")


def get_default_configuration_template(
    cls: type[DefaultConfigurationProviderProtocol],
    config: ConfigProtocol | None = None,
    files: FilesProtocol | None = None,
    plugin_name: str | None = None,
) -> JSONDict:
    _ = (config, files, plugin_name)
    default_config = cls.DEFAULT_CONFIGURATION
    if not isinstance(default_config, Mapping):
        raise ConfigError("DEFAULT_CONFIGURATION must be a mapping.")
    return copy.deepcopy(dict(default_config))


async def open_log_file_for_command(
    plugin: PluginSurfaceProtocol,
    command: Sequence[str] | None = None,
) -> io.BufferedIOBase:
    files = plugin.files
    config = plugin.config
    plugin_name = plugin.plugin_name
    if not isinstance(plugin_name, str) or not plugin_name:
        raise StateError("Plugin runtime missing plugin_name.")
    return await open_log_file(
        plugin_name=plugin_name,
        files=files,
        config=config,
        command=command,
    )
