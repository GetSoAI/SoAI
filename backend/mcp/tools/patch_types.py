"""SoAI - MCP patch operation and snapshot models [backend/mcp/tools/patch_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "AddOperation",
    "DeleteOperation",
    "FileSnapshot",
    "UpdateOperation",
)


@dataclass(frozen=True, slots=True)
class AddOperation:
    rel_path: str
    target_path: str
    content_text: str


@dataclass(frozen=True, slots=True)
class DeleteOperation:
    rel_path: str
    target_path: str
    deleted_content: str


@dataclass(frozen=True, slots=True)
class UpdateOperation:
    rel_path: str
    source_path: str
    dest_path: str
    diff_path: str
    original_text: str
    updated_text: str


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    path: str
    existed: bool
    content: bytes | None
