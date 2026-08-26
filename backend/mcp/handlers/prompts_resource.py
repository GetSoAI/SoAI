"""SoAI - MCP WebUI prompts resource handler [backend/mcp/handlers/prompts_resource.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from core.mcp.argument_numbers import parse_query_int_value
from core.mcp.content_envelopes import (
    build_json_resource_content,
    build_resource_contents_result,
)
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("read_webui_prompts_resource",)


async def read_webui_prompts_resource(
    *,
    uri: str,
    user_id: int,
    validate_prompt_color: Callable[[str | None], str | None],
    list_prompts: Callable[..., Awaitable[list[JSONDict] | None]],
    get_prompt: Callable[..., Awaitable[JSONDict | None]],
) -> JSONDict:
    parsed = urlparse(uri)
    if parsed.scheme != "soai" or parsed.netloc != "webui":
        raise MCPJSONRPCError(-32602, f"Unknown resource: {uri}")
    parts = [segment for segment in (parsed.path or "").split("/") if segment]
    if parts == ["prompts"]:
        query = parse_qs(parsed.query or "")
        search_query = (query.get("q") or [""])[0].strip()
        color_values = query.get("color")
        raw_color = color_values[0] if color_values else None
        try:
            color = validate_prompt_color(raw_color)
        except ValueError as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
        limit = (
            parse_query_int_value(
                query,
                "limit",
                build_error=lambda message: MCPJSONRPCError(-32602, message),
                integer_message=f"Invalid limit parameter: {(query.get('limit') or [''])[0]}",
                minimum_message="limit must be between 1 and 5000",
                default_value=0,
                minimum=1,
            )
            or None
        )
        if limit is not None and limit > 5000:
            raise MCPJSONRPCError(-32602, "limit must be between 1 and 5000")
        prompts = await list_prompts(user_id, color)
        prompts = prompts or []
        if search_query:
            search_query_lower = search_query.lower()
            prompts = [
                prompt
                for prompt in prompts
                if search_query_lower in str(prompt.get("name", "")).lower()
                or search_query_lower in str(prompt.get("content", "")).lower()
            ]
        if limit is not None:
            prompts = prompts[:limit]
        payload: JSONDict = {"count": len(prompts), "prompts": prompts}
        return build_resource_contents_result(build_json_resource_content(uri=uri, payload=payload))
    if len(parts) == 2 and parts[0] == "prompts":
        prompt_id = parts[1]
        prompt = await get_prompt(prompt_id, user_id)
        if not prompt:
            raise MCPJSONRPCError(-32602, f"Prompt not found: {prompt_id}")
        return build_resource_contents_result(build_json_resource_content(uri=uri, payload=prompt))
    raise MCPJSONRPCError(-32602, f"Unknown resource: {uri}")
