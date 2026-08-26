"""SoAI - MCP memory tool definitions for recall and forget [backend/mcp/tools/utility_tool_definitions/memory_recall_forget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_memory_forget_tool",
    "build_memory_recall_tool",
)


def build_memory_recall_tool(icon: JSONDict) -> JSONDict:
    return {
        "title": "Memory Recall",
        "description": (
            "Recall a specific entity from the persistent memory graph by exact name. "
            "Returns the entity with all its observations and relations."
        ),
        "icons": [icon],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Exact entity name to recall.",
                },
            },
            "required": ["name"],
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entity": {"type": ["object", "null"]},
                "found": {"type": "boolean"},
            },
            "required": ["entity", "found"],
        },
        "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
    }


def build_memory_forget_tool(icon: JSONDict) -> JSONDict:
    return {
        "title": "Memory Forget",
        "description": (
            "Remove entities, observations, or relations from the persistent memory graph. "
            "Deleting an entity cascades to its observations and relations."
        ),
        "icons": [icon],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "description": "Entity names to delete (cascades to their observations and relations).",
                },
                "observation_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "description": "Specific observation IDs to delete.",
                },
                "relation_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "description": "Specific relation IDs to delete.",
                },
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entities_deleted": {"type": "integer"},
                "observations_deleted_direct": {"type": "integer"},
                "observations_deleted_cascade": {"type": "integer"},
                "observations_deleted_total": {"type": "integer"},
                "relations_deleted_direct": {"type": "integer"},
                "relations_deleted_cascade": {"type": "integer"},
                "relations_deleted_total": {"type": "integer"},
                "records_deleted_total": {"type": "integer"},
            },
            "required": [
                "entities_deleted",
                "observations_deleted_direct",
                "observations_deleted_cascade",
                "observations_deleted_total",
                "relations_deleted_direct",
                "relations_deleted_cascade",
                "relations_deleted_total",
                "records_deleted_total",
            ],
        },
        "annotations": build_tool_annotation_flags(destructive=True, idempotent=True),
    }
