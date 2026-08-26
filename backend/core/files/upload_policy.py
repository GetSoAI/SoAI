"""SoAI - Upload temp directory policy [backend/core/files/upload_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol

__all__ = (
    "resolve_temp_directory_path",
    "resolve_temp_directory_runtime",
)


def resolve_temp_directory_runtime(
    config: ConfigProtocol,
    *,
    error_message: str = "SYSTEM.PATHS.TEMP is missing or invalid in config.yaml.",
) -> str:
    temp_dir = config.get("SYSTEM.PATHS.TEMP")
    if not isinstance(temp_dir, str):
        raise ValidationError(error_message)
    normalized_temp_dir = temp_dir.strip()
    if not normalized_temp_dir:
        raise ValidationError(error_message)
    return normalized_temp_dir


def resolve_temp_directory_path(
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
    *,
    error_message: str = "SYSTEM.PATHS.TEMP is missing or invalid in config.yaml.",
) -> str:
    return files.resolve_path(resolve_temp_directory_runtime(config, error_message=error_message))
