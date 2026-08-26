"""SoAI - Plugin path/module naming helpers [backend/plugins/path_safety.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re

from core.errors.exceptions import ValidationError
from core.files.path_policy import safe_join_relative_under_base
from core.filesystem.async_queries import async_isdir, async_listdir
from core.logging.trace import get_logger
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.plugins.runtime_services import PLUGIN_MODULE_PREFIX
from plugins.identity import (
    require_plugin_file_stem,
    require_plugin_identifier,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginDownloadManagerProtocol,
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "build_plugin_module_name",
    "build_retained_plugin_module_component",
    "get_plugin_file_path",
    "get_plugin_validation_cache_path",
    "normalize_module_component",
    "normalize_plugin_filename",
    "safe_join_plugin_dir",
    "scan_for_plugin_files",
)

LOGGER_NAME = "SoAI.plugins.path_safety"

_MODULE_COMPONENT_PATTERN = r"[^a-zA-Z0-9_]+"


def normalize_module_component(value: str) -> str:
    if not value.strip():
        raise ValidationError("Module component must be a non-empty string.")
    candidate = re.sub(_MODULE_COMPONENT_PATTERN, "_", value.strip())
    candidate = candidate.strip("_")
    if not candidate:
        raise ValidationError("Module component could not be normalized.")
    if candidate[0].isdigit():
        candidate = f"m_{candidate}"
    return candidate


def build_retained_plugin_module_component(plugin_name: str) -> str:
    normalized = normalize_module_component(plugin_name.replace("-", "_"))
    digest = hashlib.sha256(plugin_name.encode("utf-8")).hexdigest()[:16]
    return f"plugin_{normalized}_{digest}"


def build_plugin_module_name(
    *,
    plugin_name: str,
    module_name_override: str | None,
    track_module: bool,
) -> str:
    if track_module:
        component = (
            normalize_module_component(module_name_override)
            if module_name_override
            else build_retained_plugin_module_component(plugin_name)
        )
    else:
        component = (
            normalize_module_component(module_name_override)
            if module_name_override
            else normalize_module_component(plugin_name.replace("-", "_"))
        )
    return f"{PLUGIN_MODULE_PREFIX}{component}"


def safe_join_plugin_dir(manager: PluginDownloadManagerProtocol, relative_path: str) -> str:
    return safe_join_relative_under_base(
        base_path=manager.paths.plugin_directory_real,
        relative_path=relative_path,
        description="Plugin path",
        error_cls=ValidationError,
        relative_error_message="A relative plugin path is required.",
        absolute_error_message="Absolute plugin paths are not permitted.",
    )


def normalize_plugin_filename(
    manager: PluginDownloadManagerProtocol,
    filename: str,
) -> tuple[str, str]:
    invalid_message = (
        "Invalid plugin filename. Use alphanumeric characters, dashes, or underscores."
    )
    raw_name = require_plugin_file_stem(
        os.path.basename(filename),
        invalid_message=invalid_message,
    )
    return (raw_name, safe_join_plugin_dir(manager, f"{raw_name}{PLUGIN_FILE_SUFFIX}"))


def get_plugin_file_path(manager: PluginDownloadManagerProtocol, plugin_name: str) -> str:
    require_plugin_identifier(
        plugin_name,
        invalid_message=f"Invalid plugin name '{plugin_name}'.",
    )
    return safe_join_plugin_dir(manager, f"{plugin_name}{PLUGIN_FILE_SUFFIX}")


def get_plugin_validation_cache_path(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> str:
    require_plugin_identifier(plugin_name, invalid_message=f"Invalid plugin name '{plugin_name}'.")
    base_dir = str(manager.paths.temp_directory or "").strip()
    if not base_dir:
        raise ValidationError("Plugin manager temp directory is not configured.")
    return safe_join_relative_under_base(
        base_path=base_dir,
        relative_path=os.path.join("plugin_validation_cache", f"{plugin_name}.sha256"),
        description="Plugin validation cache path",
        error_cls=ValidationError,
        base_error_message="Plugin manager temp directory is not configured.",
    )


async def scan_for_plugin_files(
    path: str,
) -> list[dict[str, str]]:
    logger = get_logger(LOGGER_NAME)
    if not path:
        logger.warning("A path must be provided to scan for plugin files.")
        return []
    try:
        if await async_isdir(path):
            discovered_plugins: list[dict[str, str]] = []
            for filename in await async_listdir(path):
                if (not filename.endswith(PLUGIN_FILE_SUFFIX)) or filename.startswith("_"):
                    continue
                plugin_name = filename[: -len(PLUGIN_FILE_SUFFIX)]
                try:
                    require_plugin_identifier(
                        plugin_name,
                        invalid_message=f"Invalid plugin name '{plugin_name}'.",
                    )
                except ValidationError:
                    logger.warning(
                        "Skipping plugin file with invalid identifier '%s' during discovery.",
                        filename,
                    )
                    continue
                discovered_plugins.append({"plugin_name": plugin_name})
            return discovered_plugins
    except FileNotFoundError:
        logger.warning("Directory not found for scanning: %s", path)
    return []
