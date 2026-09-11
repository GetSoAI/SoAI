"""SoAI - MCP utility tool definition: soai_documentation [backend/mcp/tools/utility_tool_definitions/soai_documentation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.protocol.icons import ICON_DOC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_soai_documentation_tool_definitions",)


def _build_search_result_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "page": {"type": "string"},
            "page_title": {"type": "string"},
            "section": {"type": "string"},
            "heading_path": {"type": "array", "items": {"type": "string"}},
            "score": {"type": "number"},
            "content": {"type": "string"},
            "offset_chars": {"type": "integer"},
            "next_offset_chars": {"type": ["integer", "null"]},
            "truncated": {"type": "boolean"},
        },
        "required": [
            "page",
            "page_title",
            "section",
            "heading_path",
            "score",
            "content",
            "offset_chars",
            "next_offset_chars",
            "truncated",
        ],
    }


def _build_output_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mode": {"type": "string", "enum": ["search", "page"]},
            "query": {"type": "string"},
            "page": {"type": "string"},
            "page_title": {"type": "string"},
            "section": {"type": "string"},
            "content": {"type": "string"},
            "offset_chars": {"type": "integer"},
            "next_offset_chars": {"type": ["integer", "null"]},
            "returned_chars": {"type": "integer"},
            "total_chars": {"type": "integer"},
            "total_matches": {"type": "integer"},
            "returned_matches": {"type": "integer"},
            "results": {"type": "array", "items": _build_search_result_schema()},
            "truncated": {"type": "boolean"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "serialized_response_chars": {"type": "integer"},
            "max_serialized_response_chars": {"type": "integer"},
        },
        "required": [
            "mode",
            "truncated",
            "serialized_response_chars",
            "max_serialized_response_chars",
        ],
        "oneOf": [
            {
                "properties": {"mode": {"const": "search"}},
                "required": ["query", "total_matches", "returned_matches", "results"],
            },
            {
                "properties": {"mode": {"const": "page"}},
                "required": [
                    "page",
                    "page_title",
                    "section",
                    "content",
                    "offset_chars",
                    "next_offset_chars",
                    "returned_chars",
                    "total_chars",
                    "warnings",
                ],
            },
        ],
    }


def build_soai_documentation_tool_definitions() -> dict[str, JSONDict]:
    return {
        "soai_documentation": {
            "title": "SoAI Documentation",
            "description": "Search or read the offline documentation bundled with this SoAI release. Provide exactly one of query or page. Search results return canonical page IDs; continue long page reads with next_offset_chars.",
            "icons": [build_tool_icon_entry(ICON_DOC)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 4096,
                        "description": "English search phrase or exact identifier.",
                    },
                    "page": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 256,
                        "description": "Exact canonical page ID returned by search.",
                    },
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    "offset_chars": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 50000000,
                        "default": 0,
                    },
                    "max_chars": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200000,
                        "default": 20000,
                    },
                },
                "required": [],
            },
            "output_schema": _build_output_schema(),
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        }
    }
