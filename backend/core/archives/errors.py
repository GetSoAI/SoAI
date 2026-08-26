"""SoAI - Core archive extraction error types [backend/core/archives/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SecurityError

__all__ = (
    "ArchiveLinkTargetNotFoundError",
    "ArchivePathTraversalError",
)


class ArchivePathTraversalError(SecurityError): ...


class ArchiveLinkTargetNotFoundError(SecurityError): ...
