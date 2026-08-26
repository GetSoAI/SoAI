"""SoAI - Canonical MCP default tool lists [backend/core/mcp/default_tool_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.browser_tool_names import (
    BROWSER_UTILITY_MCP_TOOLS,
    PLAN_MODE_BROWSER_UTILITY_MCP_TOOLS,
)

__all__ = (
    "DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS",
    "DEFAULT_BROWSER_UTILITY_MCP_TOOLS",
    "DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS",
    "DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_TOOLS",
    "DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_WITH_STATE_TOOLS",
    "DEFAULT_CONVERSATION_MCP_PLAN_TOOLS",
    "DEFAULT_CONVERSATION_MCP_TOOLS",
    "DEFAULT_MCP_SERVER_EXPOSED_TOOLS",
    "PLAN_MODE_DEFAULT_BROWSER_UTILITY_MCP_TOOLS",
    "SUBAGENT_FORBIDDEN_UNQUALIFIED_TOOL_NAMES",
    "SUBAGENT_MCP_TOOLS",
    "VAULT_AND_CREDENTIALS_MCP_TOOLS",
)

DEFAULT_BROWSER_UTILITY_MCP_TOOLS: tuple[str, ...] = BROWSER_UTILITY_MCP_TOOLS
PLAN_MODE_DEFAULT_BROWSER_UTILITY_MCP_TOOLS: tuple[str, ...] = PLAN_MODE_BROWSER_UTILITY_MCP_TOOLS
SUBAGENT_MCP_TOOLS: tuple[str, ...] = (
    "subagent_spawn",
    "subagent_observe",
    "subagent_cancel",
)

SUBAGENT_FORBIDDEN_UNQUALIFIED_TOOL_NAMES: frozenset[str] = frozenset(
    (
        *SUBAGENT_MCP_TOOLS,
        "ask_user",
        "todo_write",
        "plan_get",
        "plan_write",
        "notify_user",
    ),
)

VAULT_AND_CREDENTIALS_MCP_TOOLS: tuple[str, ...] = (
    "vault_login_request",
    "vault_search",
    "vault_list",
    "vault_delete",
    "vault_secret_request",
)

DEFAULT_MCP_SERVER_EXPOSED_TOOLS: tuple[str, ...] = (
    "web_fetch",
    "web_search_duckduckgo",
    "web_search_searxng",
    "web_search_brave",
    "web_search_tavily",
    "web_search_serper",
    "web_search_google",
    "calculator",
    "rss_read",
    "news",
    "weather",
    "datetime_current",
    "hardware_snapshot",
    "wait",
    "random_generate",
    "hash",
    "base64",
    "text_stats",
    "unit_convert",
)

DEFAULT_CONVERSATION_MCP_TOOLS: tuple[str, ...] = (
    "calculator",
    "datetime_current",
    "stop_conversation",
    "wait",
    "unit_convert",
    "weather",
    "web_search_duckduckgo",
    "news",
    "web_fetch",
    "memory_search",
    "memory_store",
    "memory_conversation_history",
    *DEFAULT_BROWSER_UTILITY_MCP_TOOLS,
)

DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_TOOLS: tuple[str, ...] = (
    "read_file",
    "read_image",
    "read_video",
    "read_document",
    "list_dir",
    "glob_files",
    "grep_files",
)

DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_WITH_STATE_TOOLS: tuple[str, ...] = (
    *DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_TOOLS,
    "mcp_resource_read",
    "mcp_resources_list",
    "mcp_resource_templates_list",
    "plan_get",
)

DEFAULT_CONVERSATION_MCP_PLAN_TOOLS: tuple[str, ...] = (
    *SUBAGENT_MCP_TOOLS,
    "ask_user",
    "stop_conversation",
    "calculator",
    "datetime_current",
    "hardware_snapshot",
    "wait",
    *DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_TOOLS,
    "todo_write",
    "plan_get",
    "plan_write",
    "web_search_duckduckgo",
    "news",
    "web_fetch",
    "memory_search",
    "memory_conversation_history",
    *PLAN_MODE_DEFAULT_BROWSER_UTILITY_MCP_TOOLS,
)

DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS: tuple[str, ...] = (
    *SUBAGENT_MCP_TOOLS,
    "ask_user",
    "stop_conversation",
    "calculator",
    "datetime_current",
    "wait",
    "weather",
    "read_file",
    "read_image",
    "read_video",
    "read_document",
    "list_dir",
    "glob_files",
    "grep_files",
    "plan_get",
    "write_file",
    "replace_in_file",
    "apply_patch",
    "shell",
    "shell_output_read",
    "shell_output_search",
    "shell_write_stdin",
    "todo_write",
    "plan_write",
    "web_search_duckduckgo",
    "news",
    "web_fetch",
    "http_request",
    "memory_search",
    "memory_store",
    "memory_conversation_history",
    "notify_user",
    *DEFAULT_BROWSER_UTILITY_MCP_TOOLS,
    *VAULT_AND_CREDENTIALS_MCP_TOOLS,
    "browser_autofill_secret",
    "browser_autofill_vault",
)

DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS: tuple[str, ...] = (
    *SUBAGENT_MCP_TOOLS,
    "calculator",
    "datetime_current",
    "wait",
    "unit_convert",
    "read_file",
    "read_image",
    "read_video",
    "read_document",
    "list_dir",
    "glob_files",
    "grep_files",
    "plan_get",
    "write_file",
    "replace_in_file",
    "apply_patch",
    "shell",
    "shell_output_read",
    "shell_output_search",
    "shell_write_stdin",
    "todo_write",
    "plan_write",
    "web_search_duckduckgo",
    "news",
    "web_fetch",
    "http_request",
    "automation_create",
    "automation_update",
    "automation_run_enqueue",
    "automation_run_get",
    "automation_run_wait",
    "notify_user",
    *DEFAULT_BROWSER_UTILITY_MCP_TOOLS,
    *VAULT_AND_CREDENTIALS_MCP_TOOLS,
    "browser_autofill_secret",
    "browser_autofill_vault",
)
