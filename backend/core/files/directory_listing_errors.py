"""SoAI - Directory listing session errors [backend/core/files/directory_listing_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import NotFoundError

__all__ = ("DirectoryListingExpiredError",)


class DirectoryListingExpiredError(NotFoundError):
    code: str | int = "directory_listing_expired"
