"""SoAI - MCP prompt factories and request handlers [backend/mcp/registry/prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.external_service_exception import MCPError
from core.mcp.argument_validation import require_non_empty_string_value
from core.mcp.protocols_main import MCPServerProtocol
from core.mcp.validation import get_required_argument
from mcp.handlers.prompts import build_text_prompt
from mcp.protocol.catalog import build_prompt_definitions
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_prompts_get",
    "handle_prompts_list",
    "make_prompt_model_selection",
    "make_prompt_plugin_info",
    "make_prompt_system_overview",
)


def make_prompt_system_overview(
    server: MCPServerProtocol,
) -> Callable[[JSONDict], Awaitable[JSONDict]]:

    async def handler(_: JSONDict) -> JSONDict:
        text_lines = [
            "SoAI System Overview",
            "=" * 50,
            f"MCP Enabled: {server.enabled}",
            f"Host Mode: {server.host_mode_enabled}",
            f"Server Mode: {server.server_mode_enabled}",
            f"Registered Tools: {server.registered_tools_count}",
            f"Registered Resources: {server.registered_resources_count}",
            f"Registered Prompts: {server.registered_prompts_count}",
        ]
        info_service = server.model_information_service
        if info_service:
            models = await info_service.model_get_available()
            text_lines.append(f"Available Models: {len(models)}")
            for model_entry in models[:10]:
                text_lines.append(f"  - {model_entry.get('id', 'unknown')}")
            if len(models) > 10:
                text_lines.append(f"  ... and {len(models) - 10} more")
        return build_text_prompt("SoAI system overview", "\n".join(text_lines))

    return handler


def make_prompt_model_selection(
    server: MCPServerProtocol,
) -> Callable[[JSONDict], Awaitable[JSONDict]]:

    async def handler(arguments: JSONDict) -> JSONDict:
        task_type = arguments.get("task_type", "general")
        lines = [f"Model Selection for task type: {task_type}"]
        if "context_length" in arguments:
            lines.append(f"Required context length: {arguments['context_length']} tokens")
        lines.append("")
        lines.append("Available models:")
        info_service = server.model_information_service
        if info_service:
            models = await info_service.model_get_available()
            for model_entry in models:
                model_id = model_entry.get("id", "unknown")
                owner = model_entry.get("owned_by", "unknown")
                lines.append(f"- {model_id}: owned by {owner}")
        else:
            lines.append("No information service available.")
        description = f"Model selection assistant for {task_type} tasks"
        prompt_body = "\n".join(lines)
        return build_text_prompt(
            description,
            (
                f"{prompt_body}\nBased on your requirements, please select the most "
                "appropriate model."
            ),
        )

    return handler


def make_prompt_plugin_info(
    server: MCPServerProtocol,
) -> Callable[[JSONDict], Awaitable[JSONDict]]:

    async def handler(arguments: JSONDict) -> JSONDict:
        try:
            name = get_required_argument(
                arguments,
                "plugin_name",
                missing_message="Missing required parameter: plugin_name",
            )
        except MCPError as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
        plugin_list = await server.database_plugins.get_all_plugins()
        plugin = next(
            (plugin_entry for plugin_entry in plugin_list if plugin_entry.get("name") == name),
            None,
        )
        if plugin:
            text = "\n".join(
                [
                    f"Plugin Information: {name}",
                    "=" * 50,
                    f"Status: {plugin.get('state', 'unknown')}",
                    f"Version: {plugin.get('version_soaiplugin', 'unknown')}",
                    f"Description: {plugin.get('description_soaiplugin', 'No description available')}",
                    f"Plugin License: {plugin.get('license_soaiplugin', 'unknown')}",
                    f"Managed Backend License: {plugin.get('license_managed_backend', 'n/a')}",
                ],
            )
        else:
            text = f"Plugin '{name}' not found in the system."
        return build_text_prompt(f"Information about {name} plugin", text)

    return handler


async def handle_prompts_list(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
) -> JSONDict:
    prompts: list[JSONDict] = []
    prompt_definitions = build_prompt_definitions()
    for name in manager.state.registration.registered_prompts:
        definition_value = prompt_definitions.get(name)
        definition: JSONDict = definition_value if definition_value is not None else {}
        prompts.append(
            {
                key: value
                for key, value in {
                    "name": definition.get("name", name),
                    "description": definition.get("description", f"SoAI prompt: {name}"),
                    "title": definition.get("title"),
                    "arguments": definition.get("arguments"),
                    "icons": definition.get("icons"),
                }.items()
                if value is not None
            },
        )
    cursor_value = parameters.get("cursor")
    cursor = cursor_value if isinstance(cursor_value, str) else None
    page, next_cursor = manager.pagination.paginate_list(prompts, cursor)
    return {"prompts": page, **({"nextCursor": next_cursor} if next_cursor else {})}


async def handle_prompts_get(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str | None = None,
) -> JSONDict:
    try:
        name_value = get_required_argument(parameters, "name")
    except MCPError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception
    name = require_non_empty_string_value(
        name_value,
        build_error=lambda message: MCPJSONRPCError(-32602, message),
        type_message="Prompt name must be a non-empty string.",
        empty_message="Prompt name must be a non-empty string.",
    )
    arguments_value = parameters.get("arguments", {})
    arguments = arguments_value if isinstance(arguments_value, dict) else {}
    token = manager.context.set_active_client_context(client_id)
    try:
        prompt_handler = manager.state.registration.registered_prompts.get(name)
        if prompt_handler is not None:
            return await prompt_handler(arguments)
        raise MCPJSONRPCError(-32602, f"Unknown prompt: {name}")
    finally:
        manager.context.reset_active_client_context(token)
