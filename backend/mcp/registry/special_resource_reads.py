"""SoAI - MCP special resource read routing [backend/mcp/registry/special_resource_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.prompts.colors import validate_prompt_color
from mcp.calendar.resource_uris import CALENDAR_RESOURCE_URI
from mcp.calendar.resources import read_calendar_resource_uri
from mcp.handlers.prompts_resource import read_webui_prompts_resource
from mcp.handlers.resources import read_rag_resource_uri
from mcp.mail.resource_uris import MAIL_RESOURCE_URI
from mcp.mail.resources import read_mail_resource_uri
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

__all__ = ("try_read_special_resource",)


async def try_read_special_resource(
    manager: MCPRegistryManagerProtocol,
    uri: str,
) -> JSONDict | None:
    if uri.startswith(f"{MAIL_RESOURCE_URI}/"):
        _require_exposed_base_resource(manager, MAIL_RESOURCE_URI)
        user_id = manager.context.require_authenticated_user_id("Mail resources")
        return await read_mail_resource_uri(
            mail=manager.mail,
            config=manager.config,
            uri=uri,
            user_id=user_id,
        )
    if uri.startswith(f"{CALENDAR_RESOURCE_URI}/"):
        _require_exposed_base_resource(manager, CALENDAR_RESOURCE_URI)
        user_id = manager.context.require_authenticated_user_id("Calendar resources")
        return await read_calendar_resource_uri(
            calendar=manager.calendar,
            config=manager.config,
            uri=uri,
            user_id=user_id,
        )
    if uri.startswith("soai://webui/prompts"):
        user_id = manager.context.require_authenticated_user_id("WebUI prompt resources")
        return await read_webui_prompts_resource(
            uri=uri,
            user_id=user_id,
            validate_prompt_color=validate_prompt_color,
            list_prompts=manager.database_prompts.list_prompts,
            get_prompt=manager.database_prompts.get_prompt,
        )
    if uri.startswith("soai://rag/"):
        user_id = manager.context.require_authenticated_user_id("RAG resources")
        return await read_rag_resource_uri(
            uri=uri,
            user_id=user_id,
            patterns=manager.rag_resource_patterns,
            require_rag=manager.registration.require_rag,
            require_rag_user_authorization=manager.context.require_rag_user_authorization,
            require_rag_document_authorization=manager.context.require_rag_document_authorization,
            database_files=manager.database_files,
        )
    return None


def _require_exposed_base_resource(
    manager: MCPRegistryManagerProtocol,
    base_uri: str,
) -> None:
    if base_uri not in manager.registered_resources:
        raise MCPJSONRPCError(-32602, f"Unknown resource: {base_uri}")
