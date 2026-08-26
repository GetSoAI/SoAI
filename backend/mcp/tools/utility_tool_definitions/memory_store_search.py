"""SoAI - MCP memory tool definitions for store and search [backend/mcp/tools/utility_tool_definitions/memory_store_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags
from mcp.tools.utility_tool_definitions.schema_fragments import (
    build_object_input_schema,
    build_required_query_property,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_memory_search_tool",
    "build_memory_store_tool",
)


def build_memory_store_tool(icon: JSONDict) -> JSONDict:
    return {
        "title": "Memory Store",
        "description": (
            "Store knowledge in the persistent memory graph. "
            "Create entities (people, projects, concepts), add observations about them, "
            "and create relations between them. Data persists across conversations. "
            "Requires approval."
        ),
        "icons": [icon],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entities": {
                    "type": "array",
                    "description": "Entities to create or update. Each has a unique name and a type.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Unique entity name.",
                            },
                            "entity_type": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Entity type (e.g. person, project, concept, tool, language).",
                            },
                        },
                        "required": ["name", "entity_type"],
                    },
                },
                "observations": {
                    "type": "array",
                    "description": "Observations to add to existing entities.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "entity_name": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Name of the entity to attach this observation to.",
                            },
                            "content": {
                                "type": "string",
                                "minLength": 1,
                                "description": "The observation content.",
                            },
                            "source": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Optional source of this observation.",
                            },
                        },
                        "required": ["entity_name", "content"],
                    },
                },
                "relations": {
                    "type": "array",
                    "description": "Relations to create between existing entities.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "from_entity": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Source entity name.",
                            },
                            "to_entity": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Target entity name.",
                            },
                            "relation_type": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Relation type (e.g. works_on, knows, uses, depends_on).",
                            },
                        },
                        "required": ["from_entity", "to_entity", "relation_type"],
                    },
                },
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entities_inserted": {"type": "integer"},
                "entities_updated": {"type": "integer"},
                "entities_written_total": {"type": "integer"},
                "observations_inserted": {"type": "integer"},
                "relations_inserted": {"type": "integer"},
                "relations_existing": {"type": "integer"},
                "relations_written_total": {"type": "integer"},
                "entities": {"type": "array", "items": {"type": "object"}},
                "observations": {"type": "array", "items": {"type": "object"}},
                "relations": {"type": "array", "items": {"type": "object"}},
            },
            "required": [
                "entities_inserted",
                "entities_updated",
                "entities_written_total",
                "observations_inserted",
                "relations_inserted",
                "relations_existing",
                "relations_written_total",
                "entities",
                "observations",
                "relations",
            ],
        },
        "annotations": {
            **build_tool_annotation_flags(),
            "requiresApprovalHint": True,
        },
    }


def build_memory_search_tool(icon: JSONDict) -> JSONDict:
    return {
        "title": "Memory Search",
        "description": (
            "Search the persistent memory graph by keyword or wildcard. "
            "Matches entity names and observation content, ranking exact entity names first. "
            "Returns matching entities with their observations and relations. "
            "Use '*' to retrieve all entities."
        ),
        "icons": [icon],
        "input_schema": build_object_input_schema(
            properties={
                "query": build_required_query_property(
                    description="Search query (matches entity names and observation content). Use '*' to retrieve all entities.",
                ),
                "entity_type": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Filter by entity type.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return (default 10, max 50).",
                },
            },
            required=["query"],
        ),
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string"},
                "entity_type": {"type": ["string", "null"]},
                "results": {"type": "array", "items": {"type": "object"}},
                "count": {"type": "integer"},
            },
            "required": ["query", "entity_type", "results", "count"],
        },
        "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
    }
