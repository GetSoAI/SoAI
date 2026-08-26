"""SoAI - MCP/OpenAI tool handler composition [backend/mcp/bridge/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.mcp.protocols_main import MCPSearchProtocol
from core.runtime.request_context import RequestContext
from mcp.handlers.tools.builder import build_mcp_rag_tool_handlers
from mcp.search.handlers import build_mcp_search_tool_handlers
from mcp.shared.protocol_arguments import get_required_str
from mcp.tools.handlers import build_internal_utility_tool_handlers

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol
    from mcp.tools.service import MCPUtilityTools

    type ToolHandler = Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]

__all__ = ("build_builtin_tool_handlers",)


def build_builtin_tool_handlers(
    _context: RequestContext,
    user_id: int,
    conv_id: str,
    *,
    rag: MCPRAGInternalProtocol | None,
    mcp_search: MCPSearchProtocol | None,
    utility_tools: MCPUtilityTools,
    core_tool_handlers: Mapping[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]]:
    handlers: dict[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]] = dict(
        core_tool_handlers,
    )
    if rag is not None:
        handlers.update(
            build_mcp_rag_tool_handlers(
                rag,
                require_authenticated_user_id=lambda _: user_id,
                get_session_identity=lambda: (user_id, conv_id),
            ),
        )
    if mcp_search is not None:
        handlers.update(
            build_mcp_search_tool_handlers(
                mcp_search,
                get_session_identity=lambda: (user_id, conv_id),
                get_required_arg=get_required_str,
            ),
        )
    handlers.update(build_internal_utility_tool_handlers(utility_tools))
    return handlers
