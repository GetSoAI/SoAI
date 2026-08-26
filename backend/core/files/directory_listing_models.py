"""SoAI - Directory listing session models [backend/core/files/directory_listing_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.files.explorer_models import FileEntryInfo

__all__ = (
    "DirectoryListingAdmission",
    "DirectoryListingLocateResult",
    "DirectoryListingPage",
)

if TYPE_CHECKING:
    type DirectoryListingEntryType = Literal["all", "directory", "file"]
    type DirectoryListingSortColumn = Literal["modified", "name", "size", "type"]
    type DirectoryListingSortDirection = Literal["asc", "desc"]
else:
    DirectoryListingEntryType = str
    DirectoryListingSortColumn = str
    DirectoryListingSortDirection = str


@dataclass(frozen=True, slots=True)
class DirectoryListingAdmission:
    listing_id: str
    task_id: str
    path: str


@dataclass(frozen=True, slots=True)
class DirectoryListingPage:
    listing_id: str
    path: str
    entries: list[FileEntryInfo]
    total: int
    offset: int
    limit: int
    has_more: bool
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class DirectoryListingLocateResult:
    offset: int
