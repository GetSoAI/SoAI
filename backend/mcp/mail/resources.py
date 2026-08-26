"""SoAI - Mail MCP resource handlers [backend/mcp/mail/resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from core.mcp.content_envelopes import (
    build_json_resource_content,
    build_resource_contents_result,
)
from mcp.mail.resource_uris import (
    MAIL_RESOURCE_URI,
    build_mail_folder_head_resource_uri,
    build_mail_message_resource_uri,
)
from mcp.protocol.types import MCPJSONRPCError
from mcp.shared.protocol_arguments import (
    resolve_non_negative_query_int,
    resolve_optional_query_str,
    resolve_positive_query_int,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.config.protocols import ConfigProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.types.json import JSONDict

__all__ = (
    "make_resource_mail",
    "read_mail_resource_uri",
)


def make_resource_mail(server: MCPServerProtocol) -> Callable[[], Awaitable[JSONDict]]:
    async def handler() -> JSONDict:
        user_id = server.context.require_authenticated_user_id("Mail resources")
        payload = await server.mail_account_queries.list_accounts(user_id)
        return build_json_resource_content(uri=MAIL_RESOURCE_URI, payload=payload)

    return handler


async def read_mail_resource_uri(
    *,
    mail: MailServiceProtocol,
    config: ConfigProtocol,
    uri: str,
    user_id: int,
) -> JSONDict:
    parsed = urlparse(uri)
    if parsed.netloc != "mail":
        raise MCPJSONRPCError(-32602, f"Unknown mail resource: {uri}")
    path = parsed.path or ""
    query = parse_qs(parsed.query or "", keep_blank_values=False)
    if path.startswith("/messages/"):
        message_id = path.removeprefix("/messages/").strip()
        if not message_id:
            raise MCPJSONRPCError(-32602, "Mail message resource is missing message_id.")
        max_chars = resolve_positive_query_int(
            query,
            "max_chars",
            int(config.get_int("INTEGRATIONS.MAIL.LIMITS.READ_MAX_CHARS")),
        )
        offset_chars = resolve_non_negative_query_int(query, "offset_chars", 0)
        part_id = resolve_optional_query_str(query, "part_id")
        payload = await mail.read_message(
            user_id=user_id,
            message_id=message_id,
            part_id=part_id,
            max_chars=max_chars,
            offset_chars=offset_chars,
        )
        return build_resource_contents_result(
            build_json_resource_content(
                uri=build_mail_message_resource_uri(
                    message_id,
                    part_id=part_id,
                    max_chars=max_chars,
                    offset_chars=offset_chars,
                ),
                payload=payload,
            ),
        )
    if path.startswith("/folders/") and path.endswith("/head"):
        folder_id = path.removeprefix("/folders/").removesuffix("/head").strip("/")
        if not folder_id:
            raise MCPJSONRPCError(-32602, "Mail folder resource is missing folder_id.")
        limit = resolve_positive_query_int(
            query,
            "limit",
            int(config.get_int("INTEGRATIONS.MAIL.LIMITS.LIST_DEFAULT")),
        )
        order_by = resolve_optional_query_str(query, "order_by") or "received_at_ms"
        order_direction = resolve_optional_query_str(query, "order_direction") or "desc"
        search_query = resolve_optional_query_str(query, "query")
        payload = await mail.list_messages(
            user_id=user_id,
            folder_id=folder_id,
            arguments={
                "limit": limit,
                "order_by": order_by,
                "order_direction": order_direction,
                **({"query": search_query} if search_query is not None else {}),
            },
        )
        return build_resource_contents_result(
            build_json_resource_content(
                uri=build_mail_folder_head_resource_uri(
                    folder_id,
                    limit=limit,
                    order_by=order_by,
                    order_direction=order_direction,
                    query=search_query,
                ),
                payload=payload,
            ),
        )
    raise MCPJSONRPCError(-32602, f"Unknown mail resource: {uri}")
