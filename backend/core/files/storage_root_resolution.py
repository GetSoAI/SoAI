"""SoAI - Managed files storage root resolution [backend/core/files/storage_root_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.protocols import FilesPathResolverProtocol

__all__ = ("resolve_managed_files_storage_root",)


def resolve_managed_files_storage_root(
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
) -> str:
    raw_path = config.get_str("DATA.FILES.PATHS.FILES_STORAGE")
    if not raw_path:
        raise ValidationError("DATA.FILES.PATHS.FILES_STORAGE must be configured.")
    resolved_path = files.resolve_path(raw_path)
    return os.path.realpath(os.path.abspath(resolved_path))
