"""SoAI - File management types [backend/files/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Required, TypedDict

__all__ = ("FileRecord",)


class FileRecord(TypedDict, total=False):
    id: Required[str]
    size_bytes: Required[int]
    created_at: Required[int]
    filename: Required[str]
    purpose: Required[str]
    status: str
    status_details: str | None
    file_path: str
