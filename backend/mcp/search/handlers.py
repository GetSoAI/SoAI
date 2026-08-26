"""SoAI - MCP search tool handlers [backend/mcp/search/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import httpx2

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.mcp.jsonrpc_validation import (
    read_optional_jsonrpc_nonempty_str,
    read_optional_jsonrpc_nonempty_str_list,
)
from mcp.protocol.types import MCPJSONRPCError
from mcp.search.providers import get_search_provider_specs
from mcp.tools.offline_policy import build_offline_mode_error

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPSearchProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_mcp_search_tool_handlers",)


def build_mcp_search_tool_handlers(
    search: MCPSearchProtocol,
    *,
    get_session_identity: Callable[[], tuple[int, str | None]],
    get_required_arg: Callable[[JSONDict, str], str],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONDict]]]:

    def _build_optional_search_options(
        arguments: JSONDict,
        string_arguments: tuple[str, ...],
        list_arguments: tuple[str, ...],
    ) -> dict[str, JSONValue]:
        search_options: dict[str, JSONValue] = {}
        for argument_name in string_arguments:
            search_options[argument_name] = read_optional_jsonrpc_nonempty_str(
                arguments.get(argument_name),
            )
        for argument_name in list_arguments:
            search_options[argument_name] = read_optional_jsonrpc_nonempty_str_list(
                arguments.get(argument_name),
                build_error=lambda message: MCPJSONRPCError(-32602, message),
                message=f"{argument_name} must be a list of strings",
            )
        return search_options

    async def execute(
        arguments: JSONDict,
        *,
        tool_name: str,
        source: str,
        provider: str,
        search_options: dict[str, JSONValue],
    ) -> JSONDict:
        if search.runtime_flags.offline_mode:
            offline_error = build_offline_mode_error(
                tool_name=tool_name,
                capability=f"{source} search",
                url=None,
            )
            raise MCPJSONRPCError(-32603, str(offline_error))
        query = get_required_arg(arguments, "query")
        limit = coerce_positive_int(arguments.get("limit", 5), default=5, minimum=1, maximum=25)
        session_user_id, owner_id = get_session_identity()
        try:
            results = await search.search(
                query,
                limit,
                provider=provider,
                user_id=session_user_id,
                owner_id=owner_id,
                owner_type=("mcp_client" if owner_id else "conversation"),
                **search_options,
            )
            return {"query": query, "results": results, "count": len(results)}
        except ValidationError as exception:
            raise MCPJSONRPCError(-32603, f"{source} invalid response: {exception}") from exception
        except (httpx2.HTTPStatusError, httpx2.RequestError) as exception:
            raise MCPJSONRPCError(-32603, f"{source} network error: {exception}") from exception
        except TimeoutError as exception:
            raise MCPJSONRPCError(-32603, f"{source} search timed out: {exception}") from exception
        except ValueError as exception:
            raise MCPJSONRPCError(-32603, f"{source} search failed: {exception}") from exception
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            raise MCPJSONRPCError(
                -32603,
                f"{source} unexpected error: {type(exception).__name__}: {exception}",
            ) from exception

    handlers: dict[str, Callable[[JSONDict], Awaitable[JSONDict]]] = {}
    for provider in get_search_provider_specs():

        async def handler(
            arguments: JSONDict,
            provider_name: str = provider.provider_name,
            source: str = provider.handler_source,
            string_arguments: tuple[str, ...] = provider.string_arguments,
            list_arguments: tuple[str, ...] = provider.list_arguments,
        ) -> JSONDict:
            return await execute(
                arguments,
                tool_name=f"web_search_{provider_name}",
                source=source,
                provider=provider_name,
                search_options=_build_optional_search_options(
                    arguments,
                    string_arguments=string_arguments,
                    list_arguments=list_arguments,
                ),
            )

        handlers[f"web_search_{provider.provider_name}"] = handler
    return handlers
