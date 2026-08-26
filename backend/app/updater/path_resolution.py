"""SoAI - Updater-local file path resolution [backend/app/updater/path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

__all__ = ("UpdaterFilesPathResolver",)


@dataclass(frozen=True, slots=True)
class UpdaterFilesPathResolver:
    base_path: str

    def __post_init__(self) -> None:
        require_dependencies(owner="UpdaterFilesPathResolver", base_path=self.base_path)
        if not self.base_path.strip():
            raise ValidationError("UpdaterFilesPathResolver requires base_path.")

    def resolve_path(self, path: str) -> str:
        if not path.strip():
            raise ValidationError("path is required.")
        if os.path.isabs(path):
            return os.path.abspath(path)
        return os.path.abspath(os.path.join(self.base_path, path))
