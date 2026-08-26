"""SoAI - Configured files path resolver [backend/core/files/path_resolver.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.path_resolution import ConfigPathResolutionError, resolve_path
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError, ValidationError

__all__ = ("ConfigFilesPathResolver",)


class ConfigFilesPathResolver:
    def __init__(self, config: ConfigProtocol) -> None:
        self._config = config

    def resolve_path(self, path: str | os.PathLike[str]) -> str:
        if isinstance(path, os.PathLike):
            candidate = os.fspath(path)
        else:
            candidate = path
        base_path = self._config.get_str("SYSTEM.PATHS.BASE")
        if not base_path:
            raise StateError("Files helper missing a base path; cannot resolve relative paths.")
        try:
            resolved = resolve_path(candidate, base_path)
        except ConfigPathResolutionError as exception:
            raise ValidationError(str(exception)) from exception
        if resolved is None:
            raise ValidationError("resolve_path received None.")
        return resolved
