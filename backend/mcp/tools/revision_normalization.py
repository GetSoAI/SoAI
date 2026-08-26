"""SoAI - MCP revision normalization [backend/mcp/tools/revision_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("normalize_revision",)


def normalize_revision(revision_value: JSONValue | None) -> int:
    if isinstance(revision_value, bool):
        return 0
    if isinstance(revision_value, int):
        return int(max(revision_value, 0))
    if isinstance(revision_value, float):
        return int(max(int(revision_value), 0))
    if isinstance(revision_value, str):
        normalized = revision_value.strip()
        return int(normalized) if normalized.isdigit() else 0
    return 0
