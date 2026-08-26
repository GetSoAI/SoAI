"""SoAI - Storage subsystem dependency bundles [backend/hardware/storage/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.files.protocols import FilesPathResolverProtocol

__all__ = ("StorageManagerDependencies",)


@dataclass(frozen=True, slots=True)
class StorageManagerDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    base_dir: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StorageManagerDependencies",
            base_dir=self.base_dir,
            config=self.config,
            files=self.files,
        )
        if not self.base_dir.strip():
            raise ValidationError("StorageManagerDependencies requires base_dir.")
