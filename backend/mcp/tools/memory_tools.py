"""SoAI - MCP memory knowledge graph tool handlers [backend/mcp/tools/memory_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.memory_tools_validation import (
    parse_entities,
    parse_limit,
    parse_observations,
    parse_relations,
    require_dict_list,
    require_non_empty_str,
    require_str_list,
)

if TYPE_CHECKING:
    from core.mcp.protocols_storage import DatabaseMemoryProtocol
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "tool_memory_forget",
    "tool_memory_recall",
    "tool_memory_search",
    "tool_memory_store",
)

LOGGER_NAME = "SoAI.mcp.tools.memory_tools"
OPERATION_MCP_TOOLS_MEMORY_FORGET = "mcp.tools.memory_forget"
OPERATION_MCP_TOOLS_MEMORY_RECALL = "mcp.tools.memory_recall"
OPERATION_MCP_TOOLS_MEMORY_SEARCH = "mcp.tools.memory_search"
OPERATION_MCP_TOOLS_MEMORY_STORE = "mcp.tools.memory_store"
_MEMORY_STORE_KEYS = frozenset({"entities", "observations", "relations"})
_MEMORY_SEARCH_KEYS = frozenset({"query", "entity_type", "limit"})
_MEMORY_RECALL_KEYS = frozenset({"name"})
_MEMORY_FORGET_KEYS = frozenset({"entity_names", "observation_ids", "relation_ids"})
_MEMORY_AUTH_REQUIRED_MESSAGE = "Memory tools require an authenticated user session."


def _require_database_memory(utility_tools: MCPUtilityToolsProtocol) -> DatabaseMemoryProtocol:
    database_memory = utility_tools.database_memory
    if database_memory is None:
        raise MCPToolError(-32603, "Memory storage is not available.")
    return database_memory


async def tool_memory_store(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _MEMORY_STORE_KEYS)
    database_memory = _require_database_memory(utility_tools)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="memory_tools",
        message=_MEMORY_AUTH_REQUIRED_MESSAGE,
    )
    entities = parse_entities(require_dict_list(arguments, "entities"))
    observations = parse_observations(require_dict_list(arguments, "observations"))
    relations = parse_relations(require_dict_list(arguments, "relations"))
    if not entities and not observations and not relations:
        raise MCPToolError(
            -32602,
            "At least one of entities, observations, or relations must be provided.",
        )
    try:
        return await database_memory.store_graph(user_id, entities, observations, relations)
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_TOOLS_MEMORY_STORE,
        )
        log_exception(
            logger,
            coerced,
            message="Memory store operation failed.",
            operation=OPERATION_MCP_TOOLS_MEMORY_STORE,
        )
        raise MCPToolError(
            -32603,
            f"Memory store operation failed: {exception!s}",
        ) from exception


async def tool_memory_search(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _MEMORY_SEARCH_KEYS)
    database_memory = _require_database_memory(utility_tools)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="memory_tools",
        message=_MEMORY_AUTH_REQUIRED_MESSAGE,
    )
    query = require_non_empty_str(get_arg(arguments, "query"), label="query")
    entity_type_value = arguments["entity_type"] if "entity_type" in arguments else None
    entity_type: str | None = None
    if "entity_type" in arguments:
        entity_type = require_non_empty_str(entity_type_value, label="entity_type")
    limit_value = arguments["limit"] if "limit" in arguments else None
    limit = parse_limit(limit_value, provided="limit" in arguments)
    try:
        results = await database_memory.search_entities(user_id, query, entity_type, limit)
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_TOOLS_MEMORY_SEARCH,
        )
        log_exception(
            logger,
            coerced,
            message="Memory search operation failed.",
            operation=OPERATION_MCP_TOOLS_MEMORY_SEARCH,
        )
        raise MCPToolError(
            -32603,
            f"Memory search operation failed: {exception!s}",
        ) from exception
    return {
        "query": query,
        "entity_type": entity_type,
        "results": results,
        "count": len(results),
    }


async def tool_memory_recall(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _MEMORY_RECALL_KEYS)
    database_memory = _require_database_memory(utility_tools)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="memory_tools",
        message=_MEMORY_AUTH_REQUIRED_MESSAGE,
    )
    name = require_non_empty_str(get_arg(arguments, "name"), label="name")
    try:
        entity = await database_memory.get_entity(user_id, name)
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_TOOLS_MEMORY_RECALL,
        )
        log_exception(
            logger,
            coerced,
            message="Memory recall operation failed.",
            operation=OPERATION_MCP_TOOLS_MEMORY_RECALL,
        )
        raise MCPToolError(
            -32603,
            f"Memory recall operation failed: {exception!s}",
        ) from exception
    if entity is None:
        return {"entity": None, "found": False}
    return {"entity": entity, "found": True}


async def tool_memory_forget(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _MEMORY_FORGET_KEYS)
    database_memory = _require_database_memory(utility_tools)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="memory_tools",
        message=_MEMORY_AUTH_REQUIRED_MESSAGE,
    )
    entity_names = require_str_list(arguments, "entity_names")
    observation_ids = require_str_list(arguments, "observation_ids")
    relation_ids = require_str_list(arguments, "relation_ids")
    if not entity_names and not observation_ids and not relation_ids:
        raise MCPToolError(
            -32602,
            "At least one of entity_names, observation_ids, or relation_ids must be provided.",
        )
    try:
        return await database_memory.delete_graph(
            user_id,
            entity_names,
            observation_ids,
            relation_ids,
        )
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_TOOLS_MEMORY_FORGET,
        )
        log_exception(
            logger,
            coerced,
            message="Memory forget operation failed.",
            operation=OPERATION_MCP_TOOLS_MEMORY_FORGET,
        )
        raise MCPToolError(
            -32603,
            f"Memory forget operation failed: {exception!s}",
        ) from exception
