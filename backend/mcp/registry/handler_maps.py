"""SoAI - MCP handler routing maps [backend/mcp/registry/handler_maps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp.registry.completion import handle_completion_complete
from mcp.registry.internal_protocols import (
    MCPRegistryManagerProtocol,
    MCPTaskHandlerManagerProtocol,
)
from mcp.registry.prompts import handle_prompts_get, handle_prompts_list
from mcp.registry.resources import (
    handle_resource_templates_list,
    handle_resources_list,
    handle_resources_read,
    handle_resources_subscribe,
    handle_resources_unsubscribe,
)
from mcp.registry.tasks_handlers import (
    handle_tasks_cancel,
    handle_tasks_get,
    handle_tasks_list,
    handle_tasks_result,
)
from mcp.registry.tools_call import handle_tools_call
from mcp.registry.tools_list import handle_tools_list

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type ServerParametersHandler = Callable[
        [MCPRegistryManagerProtocol, JSONDict],
        Awaitable[JSONDict],
    ]
    type ServerClientHandler = Callable[
        [MCPRegistryManagerProtocol, JSONDict, str],
        Awaitable[JSONDict],
    ]
    type TaskMethodHandler = Callable[
        [MCPTaskHandlerManagerProtocol, JSONDict, str],
        Awaitable[JSONDict],
    ]

__all__ = (
    "resolve_server_mode_client_handler",
    "resolve_server_mode_params_only_handler",
    "resolve_task_method_handler",
)


def resolve_server_mode_params_only_handler(method: str) -> ServerParametersHandler | None:
    match method:
        case "tools/list":
            return handle_tools_list
        case "resources/list":
            return handle_resources_list
        case "resources/templates/list":
            return handle_resource_templates_list
        case "prompts/list":
            return handle_prompts_list
        case "completion/complete":
            return handle_completion_complete
        case _:
            return None


def resolve_server_mode_client_handler(method: str) -> ServerClientHandler | None:
    match method:
        case "resources/read":
            return handle_resources_read
        case "resources/subscribe":
            return handle_resources_subscribe
        case "resources/unsubscribe":
            return handle_resources_unsubscribe
        case "tools/call":
            return handle_tools_call
        case "prompts/get":
            return handle_prompts_get
        case _:
            return None


def resolve_task_method_handler(method: str) -> TaskMethodHandler | None:
    match method:
        case "tasks/get":
            return handle_tasks_get
        case "tasks/result":
            return handle_tasks_result
        case "tasks/list":
            return handle_tasks_list
        case "tasks/cancel":
            return handle_tasks_cancel
        case _:
            return None
