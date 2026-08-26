"""SoAI - Browser snapshot schema primitives for MCP utility tool definitions [backend/mcp/tools/utility_tool_definitions/browser_snapshot_schema_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_action_inline_snapshot_output_properties",
    "build_download_entry_properties",
    "build_downloads_output_properties",
    "build_snapshot_pagination_properties",
    "build_snapshot_payload_properties",
    "build_snapshot_refs_property",
)


def build_snapshot_refs_property() -> JSONDict:
    return {
        "refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string"},
                    "role": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
        },
    }


def build_snapshot_pagination_properties() -> JSONDict:
    return {
        "truncated": {"type": "boolean"},
        "total_chars": {"type": "integer"},
        "returned_start_char": {"type": "integer"},
        "next_start_char": {"type": ["integer", "null"]},
        "remaining_chars": {"type": "integer"},
    }


def build_snapshot_payload_properties() -> JSONDict:
    return {
        "snapshot": {"type": "string"},
        "snapshot_error": {"type": "string"},
        **build_snapshot_refs_property(),
        **build_snapshot_pagination_properties(),
    }


def build_download_entry_properties() -> JSONDict:
    return {
        "download_id": {"type": "string"},
        "url": {"type": "string"},
        "suggested_filename": {"type": "string"},
        "file_path": {"type": "string"},
        "status": {"type": "string"},
        "error": {"type": "string"},
        "timestamp": {"type": "number"},
    }


def build_downloads_output_properties() -> JSONDict:
    return {
        "downloads_dir": {"type": "string"},
        "downloads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": build_download_entry_properties(),
            },
        },
    }


def build_action_inline_snapshot_output_properties() -> JSONDict:
    return {
        "url": {"type": "string"},
        "url_changed": {"type": "boolean"},
        **build_downloads_output_properties(),
        **build_snapshot_payload_properties(),
    }
