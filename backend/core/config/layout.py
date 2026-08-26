"""SoAI - Configuration filesystem layout policy for SYSTEM.PATHS [backend/core/config/layout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.config.path_resolution import (
    ConfigPathResolutionError,
    resolve_all_paths_in_config_with_layout,
    resolve_path,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

    type ConfigDict = dict[str, ConfigValue]

__all__ = (
    "BASE_DOTTED_KEYS",
    "BASE_PATH_KEY",
    "DEFAULT_SYSTEM_DATA_PATH",
    "STATE_DOTTED_KEYS",
    "SYSTEM_DATA_PATH_KEY",
    "ConfigPathResolutionError",
    "apply_config_layout",
    "resolve_base_path",
)

DEFAULT_SYSTEM_DATA_PATH = "data"
BASE_PATH_KEY = "SYSTEM.PATHS.BASE"
SYSTEM_DATA_PATH_KEY = "SYSTEM.PATHS.SYSTEM_DATA"

STATE_DOTTED_KEYS = frozenset(
    {
        "SYSTEM.PATHS.SYSTEM_DATA",
        "DATA.DATABASE.PATHS.SYSTEM_DB",
        "SYSTEM.PATHS.TEMP",
        "DATA.FILES.PATHS.FILES_STORAGE",
        "SYSTEM.PATHS.LOCKS",
        "SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY",
        "OBSERVABILITY.LOGGING.LOGS_PATH",
        "DATA.BACKUP.BACKUPS_PATH",
        "SERVER.WEBUI.WALLPAPER_STORAGE_PATH",
        "SERVER.WEBUI.MEDIA_PREVIEWS.CACHE_STORAGE_PATH",
        "SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH",
        "TOOLS.RAG.CHROMA_PATH",
        "TOOLS.RAG.SPARSE_INDEX_DIR",
        "TOOLS.MCP.BROWSER.STORAGE_STATE_DIR",
        "TOOLS.MCP.BROWSER.USER_DATA_DIR_BASE_DIR",
        "MODELS.MANAGER.PATHS.MODELS",
        "PLUGINS.PATHS.BACKENDS",
        "PLUGINS.PATHS.VENVS_ROOT",
        "PLUGINS.PATHS.PLUGIN_LOGS",
        "PLUGINS.PATHS.TEMPLATES",
    },
)

BASE_DOTTED_KEYS = frozenset(
    {
        "SERVER.WEBUI.PATH",
        "PLUGINS.PATHS.PLUGINS",
    },
)


def resolve_base_path(
    *,
    default_base_path: str,
    configured_base_path: str | os.PathLike[str] | None,
    main_app_base_dir: str | None,
) -> str:
    base_candidate = main_app_base_dir if main_app_base_dir is not None else configured_base_path
    if not isinstance(base_candidate, str | os.PathLike):
        return default_base_path
    resolved = resolve_path(base_candidate, default_base_path)
    if resolved is None:
        raise ConfigPathResolutionError("Configured SYSTEM.PATHS.BASE did not resolve to a value.")
    return resolved


def apply_config_layout(
    config_dict: ConfigDict,
    *,
    base_path: str,
) -> str:
    system_section = config_dict.get("SYSTEM")
    if not isinstance(system_section, dict):
        raise ConfigPathResolutionError("SYSTEM must be a mapping.")
    paths_section = system_section.get("PATHS")
    if not isinstance(paths_section, dict):
        raise ConfigPathResolutionError("SYSTEM.PATHS must be a mapping.")
    system_data_candidate = paths_section.get("SYSTEM_DATA")
    raw_system_data: str | os.PathLike[str]
    if isinstance(system_data_candidate, str | os.PathLike) and str(system_data_candidate).strip():
        raw_system_data = system_data_candidate
    else:
        raw_system_data = DEFAULT_SYSTEM_DATA_PATH
    resolved_system_data = resolve_path(raw_system_data, base_path)
    if resolved_system_data is None:
        raise ConfigPathResolutionError("SYSTEM.PATHS.SYSTEM_DATA did not resolve to a value.")
    paths_section["BASE"] = base_path
    paths_section["SYSTEM_DATA"] = resolved_system_data
    resolve_all_paths_in_config_with_layout(
        config_dict,
        base_path=base_path,
        system_data_path=resolved_system_data,
        state_dotted_keys=STATE_DOTTED_KEYS,
        base_dotted_keys=BASE_DOTTED_KEYS,
    )
    return resolved_system_data
