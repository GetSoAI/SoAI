"""SoAI - MCP utility tools handler factory [backend/mcp/tools/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.types.json import JSONDict, JSONValue
from mcp.protocol.types import MCPJSONRPCError
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.ask_user import tool_ask_user
from mcp.tools.automation_tools import (
    tool_automation_create,
    tool_automation_run_enqueue,
    tool_automation_run_get,
    tool_automation_run_wait,
    tool_automation_update,
)
from mcp.tools.browser_handler_registration import build_browser_utility_tool_handlers
from mcp.tools.calculator import tool_calculator
from mcp.tools.datetime_tools import tool_datetime_current
from mcp.tools.encoding import tool_base64
from mcp.tools.error import MCPToolError, guarded_tool_call
from mcp.tools.file_grep_files import tool_grep_files
from mcp.tools.file_listing_tools import tool_glob_files, tool_list_dir
from mcp.tools.file_read_file import tool_read_file
from mcp.tools.file_write_tools import tool_replace_in_file, tool_write_file
from mcp.tools.generate_image import tool_generate_image
from mcp.tools.handler_definition_validation import (
    build_allowed_keys_by_tool_name,
    validate_utility_tool_handler_definitions,
)
from mcp.tools.hardware_benchmark import tool_hardware_benchmark
from mcp.tools.hardware_control import tool_hardware_control
from mcp.tools.hardware_snapshot import tool_hardware_snapshot
from mcp.tools.hashing import tool_hash
from mcp.tools.http_request import tool_http_request
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.mcp_resource_tools import (
    tool_mcp_resource_read,
    tool_mcp_resource_templates_list,
    tool_mcp_resources_list,
)
from mcp.tools.memory_conversation_history_tools import tool_memory_conversation_history
from mcp.tools.memory_tools import (
    tool_memory_forget,
    tool_memory_recall,
    tool_memory_search,
    tool_memory_store,
)
from mcp.tools.messaging import tool_message_parse
from mcp.tools.news import tool_news
from mcp.tools.notify_user import tool_notify_user
from mcp.tools.patch_tools import tool_apply_patch
from mcp.tools.plan_get_tools import tool_plan_get
from mcp.tools.plan_write_tools import tool_plan_write
from mcp.tools.random_tools import tool_random_generate
from mcp.tools.read_audio import tool_read_audio
from mcp.tools.read_document import tool_read_document
from mcp.tools.read_image import tool_read_image
from mcp.tools.read_video import tool_read_video
from mcp.tools.rss import tool_rss_read
from mcp.tools.shell import tool_shell
from mcp.tools.shell_output_tools import tool_shell_output_read, tool_shell_output_search
from mcp.tools.shell_write_stdin import tool_shell_write_stdin
from mcp.tools.stop_conversation import tool_stop_conversation
from mcp.tools.subagent_tools import (
    tool_subagent_cancel,
    tool_subagent_observe,
    tool_subagent_spawn,
)
from mcp.tools.text_stats import tool_text_stats
from mcp.tools.todo_write_tools import tool_todo_write
from mcp.tools.unit_conversion import tool_unit_convert
from mcp.tools.utility_definitions import (
    build_internal_utility_tool_definitions,
    build_public_utility_tool_definitions,
)
from mcp.tools.vault_delete import tool_vault_delete
from mcp.tools.vault_list import tool_vault_list
from mcp.tools.vault_login_request import tool_vault_login_request
from mcp.tools.vault_search import tool_vault_search
from mcp.tools.vault_secret_request import tool_vault_secret_request
from mcp.tools.wait import tool_wait
from mcp.tools.weather import tool_weather

__all__ = (
    "build_internal_utility_tool_handlers",
    "build_public_utility_tool_handlers",
)


def _build_utility_tool_handlers(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    include_internal: bool,
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    definitions = (
        build_internal_utility_tool_definitions()
        if include_internal
        else build_public_utility_tool_definitions()
    )
    allowed_keys_by_tool_name = build_allowed_keys_by_tool_name(definitions)

    def build_handler(
        tool_name: str,
        tool_func: Callable[[JSONDict], Awaitable[JSONValue]],
    ) -> Callable[[JSONDict], Awaitable[JSONValue]]:

        async def handler(arguments: JSONDict) -> JSONValue:
            try:
                allowed_keys = allowed_keys_by_tool_name.get(tool_name)
                if allowed_keys is not None:
                    reject_unexpected_parameters(arguments, allowed_keys)
                operation = f"mcp.tools.{tool_name}"
                return await guarded_tool_call(operation, tool_name, tool_func(arguments))
            except MCPToolError as exception:
                raise MCPJSONRPCError(
                    exception.rpc_code,
                    exception.message,
                    exception.data,
                ) from exception

        return handler

    def bind_tool(
        tool_func: Callable[[MCPUtilityToolsProtocol, JSONDict], Awaitable[JSONValue]],
    ) -> Callable[[JSONDict], Awaitable[JSONValue]]:
        async def bound_handler(arguments: JSONDict) -> JSONValue:
            return await tool_func(utility_tools, arguments)

        return bound_handler

    handlers = {
        "subagent_spawn": build_handler("subagent_spawn", bind_tool(tool_subagent_spawn)),
        "subagent_observe": build_handler(
            "subagent_observe",
            bind_tool(tool_subagent_observe),
        ),
        "subagent_cancel": build_handler("subagent_cancel", bind_tool(tool_subagent_cancel)),
        **build_browser_utility_tool_handlers(
            build_handler=build_handler,
            bind_tool=bind_tool,
        ),
        "read_audio": build_handler("read_audio", bind_tool(tool_read_audio)),
        "ask_user": build_handler("ask_user", bind_tool(tool_ask_user)),
        "vault_secret_request": build_handler(
            "vault_secret_request", bind_tool(tool_vault_secret_request)
        ),
        "vault_login_request": build_handler(
            "vault_login_request",
            bind_tool(tool_vault_login_request),
        ),
        "vault_list": build_handler("vault_list", bind_tool(tool_vault_list)),
        "vault_search": build_handler("vault_search", bind_tool(tool_vault_search)),
        "vault_delete": build_handler("vault_delete", bind_tool(tool_vault_delete)),
        "automation_create": build_handler("automation_create", bind_tool(tool_automation_create)),
        "automation_update": build_handler("automation_update", bind_tool(tool_automation_update)),
        "automation_run_enqueue": build_handler(
            "automation_run_enqueue",
            bind_tool(tool_automation_run_enqueue),
        ),
        "automation_run_get": build_handler(
            "automation_run_get",
            bind_tool(tool_automation_run_get),
        ),
        "automation_run_wait": build_handler(
            "automation_run_wait",
            bind_tool(tool_automation_run_wait),
        ),
        "calculator": build_handler("calculator", bind_tool(tool_calculator)),
        "rss_read": build_handler("rss_read", bind_tool(tool_rss_read)),
        "news": build_handler("news", bind_tool(tool_news)),
        "weather": build_handler("weather", bind_tool(tool_weather)),
        "datetime_current": build_handler("datetime_current", bind_tool(tool_datetime_current)),
        "hardware_snapshot": build_handler("hardware_snapshot", bind_tool(tool_hardware_snapshot)),
        "wait": build_handler("wait", bind_tool(tool_wait)),
        "random_generate": build_handler("random_generate", bind_tool(tool_random_generate)),
        "notify_user": build_handler("notify_user", bind_tool(tool_notify_user)),
        "hash": build_handler("hash", bind_tool(tool_hash)),
        "base64": build_handler("base64", bind_tool(tool_base64)),
        "text_stats": build_handler("text_stats", bind_tool(tool_text_stats)),
        "unit_convert": build_handler("unit_convert", bind_tool(tool_unit_convert)),
        "message_parse": build_handler("message_parse", bind_tool(tool_message_parse)),
        "generate_image": build_handler("generate_image", bind_tool(tool_generate_image)),
        "shell": build_handler("shell", bind_tool(tool_shell)),
        "shell_output_read": build_handler(
            "shell_output_read",
            bind_tool(tool_shell_output_read),
        ),
        "shell_output_search": build_handler(
            "shell_output_search",
            bind_tool(tool_shell_output_search),
        ),
        "shell_write_stdin": build_handler("shell_write_stdin", bind_tool(tool_shell_write_stdin)),
        "read_file": build_handler("read_file", bind_tool(tool_read_file)),
        "read_image": build_handler("read_image", bind_tool(tool_read_image)),
        "read_video": build_handler("read_video", bind_tool(tool_read_video)),
        "read_document": build_handler("read_document", bind_tool(tool_read_document)),
        "list_dir": build_handler("list_dir", bind_tool(tool_list_dir)),
        "grep_files": build_handler("grep_files", bind_tool(tool_grep_files)),
        "apply_patch": build_handler("apply_patch", bind_tool(tool_apply_patch)),
        "todo_write": build_handler("todo_write", bind_tool(tool_todo_write)),
        "plan_get": build_handler("plan_get", bind_tool(tool_plan_get)),
        "plan_write": build_handler("plan_write", bind_tool(tool_plan_write)),
        "mcp_resources_list": build_handler(
            "mcp_resources_list",
            bind_tool(tool_mcp_resources_list),
        ),
        "mcp_resource_templates_list": build_handler(
            "mcp_resource_templates_list",
            bind_tool(tool_mcp_resource_templates_list),
        ),
        "mcp_resource_read": build_handler("mcp_resource_read", bind_tool(tool_mcp_resource_read)),
        "replace_in_file": build_handler("replace_in_file", bind_tool(tool_replace_in_file)),
        "write_file": build_handler("write_file", bind_tool(tool_write_file)),
        "glob_files": build_handler("glob_files", bind_tool(tool_glob_files)),
        "http_request": build_handler("http_request", bind_tool(tool_http_request)),
        "memory_store": build_handler("memory_store", bind_tool(tool_memory_store)),
        "memory_search": build_handler("memory_search", bind_tool(tool_memory_search)),
        "memory_recall": build_handler("memory_recall", bind_tool(tool_memory_recall)),
        "memory_forget": build_handler("memory_forget", bind_tool(tool_memory_forget)),
        "memory_conversation_history": build_handler(
            "memory_conversation_history",
            bind_tool(tool_memory_conversation_history),
        ),
    }
    if include_internal:
        handlers["stop_conversation"] = build_handler(
            "stop_conversation",
            bind_tool(tool_stop_conversation),
        )
        handlers["hardware_benchmark"] = build_handler(
            "hardware_benchmark",
            bind_tool(tool_hardware_benchmark),
        )
        handlers["hardware_control"] = build_handler(
            "hardware_control",
            bind_tool(tool_hardware_control),
        )
    validate_utility_tool_handler_definitions(
        definitions=definitions,
        handlers=handlers,
    )
    return handlers


def build_public_utility_tool_handlers(
    utility_tools: MCPUtilityToolsProtocol,
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    return _build_utility_tool_handlers(utility_tools, include_internal=False)


def build_internal_utility_tool_handlers(
    utility_tools: MCPUtilityToolsProtocol,
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    return _build_utility_tool_handlers(utility_tools, include_internal=True)
