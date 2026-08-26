"""SoAI - File operations for plugin runtime [backend/plugin_sdk/filesystem/files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.files.path_resolver import ConfigFilesPathResolver
from core.filesystem.path_coercion import coerce_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = ("Files",)


@dataclass(slots=True)
class Files:
    config: ConfigProtocol

    def resolve_path(self, path: PathInput) -> str:
        candidate = coerce_path(path)
        return ConfigFilesPathResolver(self.config).resolve_path(candidate)
