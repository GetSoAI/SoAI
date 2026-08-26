"""SoAI - TAR extraction plan records [backend/core/archives/tar_plan_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import tarfile
from dataclasses import dataclass

__all__ = ("TarCopyOperation", "TarExtractionPlan", "TarLinkMember")


@dataclass(frozen=True, slots=True)
class TarCopyOperation:
    source_path: str
    destination_path: str
    file_size: int


@dataclass(frozen=True, slots=True)
class TarLinkMember:
    destination_path: str
    raw_target: str
    resolved_target: str
    is_symbolic: bool


@dataclass(frozen=True, slots=True)
class TarExtractionPlan:
    directories: tuple[str, ...]
    regular_members: tuple[tarfile.TarInfo, ...]
    copy_operations: tuple[TarCopyOperation, ...]
    total_size: int
