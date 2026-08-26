"""SoAI - Configuration path resolution [backend/app/config/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.files.path_policy import ensure_path_within_base
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX

__all__ = (
    "get_config_path_sync",
    "path_to_config_name",
    "resolve_base_path",
    "resolve_plugins_path",
)


def resolve_base_path(base_path: str) -> str:
    candidate = base_path.strip()
    if not candidate:
        raise ValidationError("base_path must be provided.")
    return os.path.abspath(candidate)


def resolve_plugins_path(plugin_directory: str | None) -> str | None:
    if plugin_directory is None:
        return None
    if not isinstance(plugin_directory, str):
        raise ValidationError("plugin_directory must be a string when provided.")
    if not plugin_directory.strip():
        return None
    return os.path.abspath(plugin_directory)


def get_config_path_sync(
    *,
    core_config_path: str,
    plugins_path: str | None,
    config_name: str,
) -> str:
    if config_name == "core":
        if not core_config_path.strip():
            raise ValidationError("core_config_path must be provided for core config.")
        return os.path.abspath(core_config_path)
    if ".." in config_name or "/" in config_name or "\\" in config_name:
        raise ValidationError(f"Invalid config name: {config_name}")
    if not plugins_path:
        raise StateError("Plugin directory not set. Cannot determine plugin config path.")
    return os.path.join(plugins_path, f"{config_name}{PLUGIN_CONFIG_FILE_SUFFIX}")


def path_to_config_name(
    *,
    core_config_path: str,
    plugins_path: str | None,
    path: str,
) -> str | None:
    resolved_path = os.path.abspath(path)
    if resolved_path == get_config_path_sync(
        core_config_path=core_config_path,
        plugins_path=plugins_path,
        config_name="core",
    ):
        return "core"
    if not plugins_path:
        return None
    if not resolved_path.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
        return None
    try:
        ensure_path_within_base(
            plugins_path,
            resolved_path,
            description="Plugin config path",
        )
    except ValueError:
        return None
    return os.path.basename(resolved_path).removesuffix(PLUGIN_CONFIG_FILE_SUFFIX)
