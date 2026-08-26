"""SoAI - Shared MCP tool annotation profiles [backend/mcp/shared/tool_annotations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.schema import build_tool_annotation_flags

__all__ = ("build_tool_annotation_profiles",)


def build_tool_annotation_profiles() -> tuple[dict[str, bool], dict[str, bool], dict[str, bool]]:
    read_only_annotations = build_tool_annotation_flags(
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=True,
    )
    sync_annotations = build_tool_annotation_flags(
        read_only=False,
        destructive=False,
        idempotent=True,
        open_world=True,
    )
    destructive_annotations = build_tool_annotation_flags(
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=True,
    )
    return (read_only_annotations, sync_annotations, destructive_annotations)
