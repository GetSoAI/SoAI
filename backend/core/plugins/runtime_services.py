"""SoAI - Plugin runtime service container types [backend/core/plugins/runtime_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.plugins.model_variants import normalize_variant_name
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.protocols_runtime import (
    PluginHardwareRuntimeProtocol,
    PluginManagerRuntimeServiceProtocol,
    PluginMetricsRuntimeProtocol,
    PluginModelRegistryRuntimeProtocol,
    PluginRuntimeFailureReporterProtocol,
    PluginRuntimeFlagsProtocol,
    PluginStorageRuntimeProtocol,
)
from core.types.protocols import HttpClientProtocol

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput
    from core.types.json import JSONDict

__all__ = (
    "PLUGIN_MODULE_PREFIX",
    "UNLOAD_ALL_MODELS_SENTINEL",
    "PluginHardwareRuntimeProtocol",
    "PluginManagerRuntimeServiceProtocol",
    "PluginMetricsRuntimeProtocol",
    "PluginModelRegistryRuntimeProtocol",
    "PluginPathResolver",
    "PluginRuntimeFlagsProtocol",
    "PluginRuntimeFailureReporterProtocol",
    "PluginRuntimeServices",
    "PluginStorageRuntimeProtocol",
)

UNLOAD_ALL_MODELS_SENTINEL = "Unload All Models"
PLUGIN_MODULE_PREFIX = "soai_plugin_"


@dataclass(frozen=True, slots=True)
class PluginRuntimeServices:
    metrics_manager: PluginMetricsRuntimeProtocol
    model_registry: PluginModelRegistryRuntimeProtocol
    plugin_manager: PluginManagerRuntimeServiceProtocol
    runtime_reporter: PluginRuntimeFailureReporterProtocol
    hw_manager: PluginHardwareRuntimeProtocol | None
    storage_manager: PluginStorageRuntimeProtocol
    runtime_flags: PluginRuntimeFlagsProtocol
    files: FilesProtocol
    plugin_config: JSONDict
    http_client: HttpClientProtocol
    install_path: str | None


class PluginPathResolver:
    def __init__(
        self,
        plugin_name: str,
        config: ConfigProtocol,
        files: FilesProtocol,
        plugin_config: JSONDict | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.config = config
        self.files = files
        self.plugin_config = plugin_config if plugin_config is not None else {}

    def models_directory(self) -> str:
        override_value = self.plugin_config.get("MODELS_PATH_OVERRIDE")
        override = (
            override_value.strip()
            if isinstance(override_value, str) and override_value.strip()
            else None
        )
        if override:
            return self.files.resolve_path(override)
        base_dir = self.config.require_str("MODELS.MANAGER.PATHS.MODELS")
        return self.files.resolve_path(os.path.join(base_dir, self.plugin_name))

    def resolve(self, path: PathInput) -> str:
        normalized_path = path
        if isinstance(normalized_path, os.PathLike):
            normalized_path = os.fspath(normalized_path)
        if isinstance(normalized_path, str) and not normalized_path.strip():
            raise ValidationError("Path must not be empty.")
        resolved_path = self.files.resolve_path(normalized_path)
        if not resolved_path:
            raise ValidationError("Resolved path must not be empty.")
        return resolved_path

    def plugin_cache_root(self) -> str:
        root = os.path.join(self._require_system_data_path(), "plugins", self.plugin_name)
        os.makedirs(root, exist_ok=True)
        return root

    def cache_path(self, *parts: PathInput, ensure_parent: bool = True) -> str:
        root = self.plugin_cache_root()
        segments: list[str] = []
        for raw_part in parts:
            if raw_part is None:
                continue
            part = os.fspath(raw_part) if isinstance(raw_part, os.PathLike) else raw_part
            text = str(part).strip("/\\")
            if text:
                segments.append(text)
        path = os.path.join(root, *segments) if segments else root
        if ensure_parent:
            parent = path if os.path.isdir(path) else os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        return path

    def temp_directory(self, token: str | None = None) -> str:
        base = os.path.join(self._require_system_data_path(), "temp", "plugins", self.plugin_name)
        os.makedirs(base, exist_ok=True)
        if not token:
            return base
        subdirectory = os.path.join(base, normalize_variant_name(str(token)))
        os.makedirs(subdirectory, exist_ok=True)
        return subdirectory

    def _require_system_data_path(self) -> str:
        return self.config.require_str("SYSTEM.PATHS.SYSTEM_DATA")
