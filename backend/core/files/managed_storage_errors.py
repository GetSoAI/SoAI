"""SoAI - Managed storage security errors [backend/core/files/managed_storage_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SecurityError

__all__ = (
    "FileDeletionSecurityError",
    "FileStorageSecurityError",
)


class FileStorageSecurityError(SecurityError): ...


class FileDeletionSecurityError(FileStorageSecurityError): ...
