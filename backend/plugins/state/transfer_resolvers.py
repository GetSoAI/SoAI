"""SoAI - Default plugin manager transfer and path resolvers [backend/plugins/state/transfer_resolvers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.runtime_support import initialize_temp_directory

__all__ = ()


def default_plugin_path_resolver(
    plugin_directory: str,
    backends_directory: str,
) -> tuple[str, str, str]:
    plugin_abs = os.path.abspath(plugin_directory)
    backends_abs = os.path.abspath(backends_directory)
    plugin_real = os.path.realpath(plugin_abs)
    return (plugin_abs, backends_abs, plugin_real)


def default_transfer_flag_resolver(
    config: ConfigProtocol,
) -> tuple[bool, bool, bool]:
    uploads_enabled = config.get_bool("PLUGINS.FEATURES.UPLOADS")
    downloads_enabled = config.get_bool("PLUGINS.FEATURES.DOWNLOADS")
    allow_insecure_downloads = config.get_bool("PLUGINS.SECURITY.ALLOW_INSECURE_DOWNLOADS")
    return (uploads_enabled, downloads_enabled, allow_insecure_downloads)


def default_temp_directory_resolver(files: FilesProtocol, config: ConfigProtocol) -> str:
    raw_temp = initialize_temp_directory(config)
    return files.resolve_path(raw_temp)


def default_plugin_venvs_root_resolver(files: FilesProtocol, config: ConfigProtocol) -> str:
    venvs_root_value = config.get_str("PLUGINS.PATHS.VENVS_ROOT")
    venvs_root = venvs_root_value.strip() if isinstance(venvs_root_value, str) else ""
    if not venvs_root:
        raise StateError(
            "Config is missing PLUGINS.PATHS.VENVS_ROOT; cannot resolve plugin env root.",
        )
    return files.resolve_path(venvs_root)
