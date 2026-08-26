"""SoAI - Agent tool context payload helpers [backend/features/agent/runtime/tool_context_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.default_tool_names import (
    DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_WITH_STATE_TOOLS,
)
from core.mcp.mail_calendar_tool_names import MAIL_CALENDAR_MCP_TOOL_NAMES
from core.mcp.qualified_name import decode_qualified_tool_name
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict

__all__ = (
    "build_tool_payload_entries",
    "collect_profiles_from_tool_payloads",
)

_WEB_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "web_fetch",
        "knowledge_web_fetch",
        "web_search_duckduckgo",
        "news",
        "knowledge_search",
        "http_request",
        "generate_image",
        "weather",
        "rss_read",
    },
)
_SHELL_TOOL_NAMES: frozenset[str] = frozenset(
    {"shell", "shell_output_read", "shell_output_search", "shell_write_stdin"},
)
_FS_READ_TOOL_NAMES: tuple[str, ...] = DEFAULT_CONVERSATION_MCP_FILESYSTEM_READ_WITH_STATE_TOOLS
_FS_WRITE_TOOL_NAMES: frozenset[str] = frozenset({"apply_patch", "replace_in_file", "write_file"})
_PLANNING_TOOL_NAMES: frozenset[str] = frozenset(
    {"todo_write", "plan_write", "plan_get"},
)
_MEMORY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "memory_store",
        "memory_search",
        "memory_recall",
        "memory_forget",
        "memory_conversation_history",
    },
)
_CREDENTIAL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "browser_autofill_secret",
        "browser_autofill_vault",
        "vault_secret_request",
        "vault_delete",
        "vault_list",
        "vault_login_request",
        "vault_search",
    },
)
_BROWSER_RECOVERY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "browser_console",
        "browser_dialog",
        "browser_downloads",
        "browser_network",
        "browser_persistence_reset",
        "browser_profiles",
        "browser_status",
    },
)
_BROWSER_EXTERNAL_EFFECT_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "browser_autofill_secret",
        "browser_autofill_vault",
        "browser_click",
        "browser_close",
        "browser_dialog",
        "browser_drag",
        "browser_eval",
        "browser_hover",
        "browser_navigate",
        "browser_persistence_reset",
        "browser_press_key",
        "browser_resize",
        "browser_screenshot",
        "browser_select_option",
        "browser_tabs",
        "browser_type",
        "browser_upload_file",
    },
)
_SESSION_COORDINATION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "browser_tabs",
        "browser_status",
        "browser_profiles",
        "browser_snapshot",
    },
)
_BACKGROUND_WORKFLOW_TOOL_NAMES: frozenset[str] = frozenset(
    {"wait", "notify_user", "automation_run_wait"},
)
_AUTOMATION_TOOL_PREFIX = "automation_"
_SUBAGENT_TOOL_PREFIX = "subagent_"
_EXTERNAL_EFFECT_TOOL_NAMES: frozenset[str] = frozenset(
    {"generate_image", "http_request", "memory_forget", "memory_store", "notify_user"},
)


def _extract_annotation_bool(tool_entry: JSONDict, annotation_name: str) -> bool | None:
    raw = coerce_json_dict(tool_entry.get("raw"))
    if raw is None:
        return None
    annotations = coerce_json_dict(raw.get("annotations"))
    if annotations is None:
        return None
    annotation_value = annotations.get(annotation_name)
    if isinstance(annotation_value, bool):
        return annotation_value
    return None


def _classify_tool_category(decoded_name: str) -> str:
    if decoded_name == "ask_user":
        return "ask_user"
    if decoded_name in _PLANNING_TOOL_NAMES:
        return "planning"
    if decoded_name in _MEMORY_TOOL_NAMES:
        return "memory"
    if decoded_name in _SHELL_TOOL_NAMES:
        return "shell"
    if decoded_name in _FS_WRITE_TOOL_NAMES:
        return "fs_write"
    if decoded_name in _FS_READ_TOOL_NAMES:
        return "fs_read"
    if decoded_name in _WEB_TOOL_NAMES:
        return "web"
    if decoded_name.startswith("browser_"):
        return "browser"
    return "other"


def _tool_has_external_effect(decoded_name: str, category: str, destructive: bool | None) -> bool:
    if destructive is True:
        return True
    if category in {"fs_write", "shell"}:
        return True
    if decoded_name in _EXTERNAL_EFFECT_TOOL_NAMES:
        return True
    if decoded_name in _BROWSER_EXTERNAL_EFFECT_TOOL_NAMES:
        return True
    return decoded_name.startswith(_AUTOMATION_TOOL_PREFIX)


def build_tool_payload_entries(
    *,
    tool_names: list[str],
    tool_entries: dict[str, JSONDict],
) -> list[JSONDict]:
    payload_entries: list[JSONDict] = []
    for original_name in tool_names:
        server_id, decoded_name = decode_qualified_tool_name(original_name)
        entry = tool_entries.get(original_name)
        read_only = (
            _extract_annotation_bool(entry, "readOnlyHint") if isinstance(entry, dict) else None
        )
        destructive = (
            _extract_annotation_bool(entry, "destructiveHint") if isinstance(entry, dict) else None
        )
        idempotent = (
            _extract_annotation_bool(entry, "idempotentHint") if isinstance(entry, dict) else None
        )
        open_world = (
            _extract_annotation_bool(entry, "openWorldHint") if isinstance(entry, dict) else None
        )
        category = _classify_tool_category(decoded_name)
        payload_entries.append(
            {
                "name": original_name,
                "source": server_id if server_id else "local",
                "category": category,
                "read_only": read_only,
                "destructive": destructive,
                "idempotent": idempotent,
                "open_world": open_world,
                "external_effect": _tool_has_external_effect(decoded_name, category, destructive),
            },
        )
    return payload_entries


def collect_profiles_from_tool_payloads(tools: list[JSONDict]) -> JSONDict:
    decoded_names = {decode_qualified_tool_name(str(tool.get("name") or ""))[1] for tool in tools}
    has_browser = any(tool.get("category") == "browser" for tool in tools)
    has_web = any(tool.get("category") == "web" for tool in tools)
    has_shell = any(tool.get("category") == "shell" for tool in tools)
    has_fs_read = any(tool.get("category") == "fs_read" for tool in tools)
    has_fs_write = any(tool.get("category") == "fs_write" for tool in tools)
    has_memory = any(tool.get("category") == "memory" for tool in tools)
    has_ask_user = any(tool.get("category") == "ask_user" for tool in tools)
    has_automation = any(name.startswith(_AUTOMATION_TOOL_PREFIX) for name in decoded_names)
    has_subagents = any(name.startswith(_SUBAGENT_TOOL_PREFIX) for name in decoded_names)
    has_browser_recovery = bool(decoded_names & _BROWSER_RECOVERY_TOOL_NAMES)
    return {
        "browser": has_browser,
        "web": has_web,
        "shell": has_shell,
        "fs_read": has_fs_read,
        "fs_write": has_fs_write,
        "ask_user": has_ask_user,
        "planning": any(tool.get("category") == "planning" for tool in tools),
        "memory": has_memory,
        "credentials": bool(decoded_names & _CREDENTIAL_TOOL_NAMES),
        "local_execution": bool(has_shell or has_fs_read or has_fs_write),
        "live_research": bool(has_browser or has_web),
        "browser_recovery": has_browser_recovery,
        "automation": has_automation,
        "interactive_checkpointing": bool(has_ask_user),
        "session_coordination": bool(
            has_browser
            and bool(
                decoded_names & (_SESSION_COORDINATION_TOOL_NAMES | _BROWSER_RECOVERY_TOOL_NAMES),
            ),
        ),
        "authoring": bool(has_browser or has_fs_write),
        "mail_calendar_mcp": any(
            tool_name in decoded_names for tool_name in MAIL_CALENDAR_MCP_TOOL_NAMES
        ),
        "verification_surface": bool(has_browser or has_web or has_shell or has_fs_read),
        "external_effects": any(bool(tool.get("external_effect")) for tool in tools),
        "background_workflows": bool(
            has_automation or bool(decoded_names & _BACKGROUND_WORKFLOW_TOOL_NAMES),
        ),
        "subagents": has_subagents,
    }
