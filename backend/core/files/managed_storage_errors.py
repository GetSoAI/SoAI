"""SoAI - Managed storage security errors [backend/core/files/managed_storage_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ConflictError, SecurityError

__all__ = (
    "FileDeletionSecurityError",
    "FileStorageSecurityError",
    "FileInUseError",
)


class FileStorageSecurityError(SecurityError): ...


class FileDeletionSecurityError(FileStorageSecurityError): ...


class FileInUseError(ConflictError):
    code: str | int = "file_in_use"
    http_status = 423
    public_message: str | None = (
        "The file is in use by another application. Close that application and retry."
    )
