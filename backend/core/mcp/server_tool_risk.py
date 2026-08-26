"""SoAI - MCP server-mode high-impact capability catalog [backend/core/mcp/server_tool_risk.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.browser_tool_names import BROWSER_UTILITY_MCP_TOOLS
from core.mcp.filesystem_tool_names import FILESYSTEM_MCP_TOOL_NAMES
from core.mcp.mail_calendar_tool_names import MAIL_CALENDAR_MCP_TOOL_NAMES

__all__ = (
    "MCP_SERVER_AUTONOMOUS_EXECUTION_TOOLS",
    "MCP_SERVER_BROWSER_TOOLS",
    "MCP_SERVER_CONNECTED_ACCOUNT_TOOLS",
    "MCP_SERVER_CREDENTIAL_TOOLS",
    "MCP_SERVER_FILESYSTEM_TOOLS",
    "MCP_SERVER_HOST_COMMAND_TOOLS",
    "MCP_SERVER_OPEN_HTTP_TOOLS",
    "MCP_SERVER_PERSISTENT_MUTATION_TOOLS",
    "MCP_SERVER_PRIVATE_CONTEXT_TOOLS",
    "MCP_SERVER_RESOURCE_INTENSIVE_TOOLS",
    "MCP_SERVER_SENSITIVE_RESOURCES",
)

MCP_SERVER_HOST_COMMAND_TOOLS: tuple[str, ...] = (
    "shell",
    "shell_output_read",
    "shell_output_search",
    "shell_write_stdin",
)

MCP_SERVER_FILESYSTEM_TOOLS: tuple[str, ...] = FILESYSTEM_MCP_TOOL_NAMES

MCP_SERVER_BROWSER_TOOLS: tuple[str, ...] = (
    *BROWSER_UTILITY_MCP_TOOLS,
    "browser_autofill_secret",
    "browser_autofill_vault",
)

MCP_SERVER_CONNECTED_ACCOUNT_TOOLS: tuple[str, ...] = MAIL_CALENDAR_MCP_TOOL_NAMES

MCP_SERVER_CREDENTIAL_TOOLS: tuple[str, ...] = (
    "browser_autofill_secret",
    "browser_autofill_vault",
    "vault_delete",
    "vault_list",
    "vault_login_request",
    "vault_search",
    "vault_secret_request",
)

MCP_SERVER_AUTONOMOUS_EXECUTION_TOOLS: tuple[str, ...] = (
    "automation_create",
    "automation_run_enqueue",
    "automation_run_get",
    "automation_run_wait",
    "automation_update",
    "subagent_cancel",
    "subagent_observe",
    "subagent_spawn",
)

MCP_SERVER_PERSISTENT_MUTATION_TOOLS: tuple[str, ...] = (
    "knowledge_reindex",
    "knowledge_web_fetch",
    "memory_forget",
    "memory_store",
    "notify_user",
    "plan_write",
    "todo_write",
)

MCP_SERVER_PRIVATE_CONTEXT_TOOLS: tuple[str, ...] = (
    "ask_user",
    "knowledge_config_get",
    "knowledge_list",
    "knowledge_search",
    "mcp_resource_read",
    "mcp_resource_templates_list",
    "mcp_resources_list",
    "memory_conversation_history",
    "memory_recall",
    "memory_search",
    "plan_get",
)

MCP_SERVER_RESOURCE_INTENSIVE_TOOLS: tuple[str, ...] = (
    "generate_image",
    "knowledge_reindex",
    "read_audio",
    "read_document",
    "read_video",
)

MCP_SERVER_OPEN_HTTP_TOOLS: tuple[str, ...] = ("http_request",)

MCP_SERVER_SENSITIVE_RESOURCES: tuple[str, ...] = ("calendar", "mail")
