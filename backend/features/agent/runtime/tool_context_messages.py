"""SoAI - Agent tool context prompt helpers [backend/features/agent/runtime/tool_context_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypedDict

from core.agent_mode import normalize_agent_mode
from core.prompts.system_prompts import (
    get_text_prompt_v1,
    render_text_prompt_template_v1,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict
from features.agent.runtime.tool_context_profiles import (
    build_tool_payload_entries,
    collect_profiles_from_tool_payloads,
)
from features.agent.runtime.tool_prompt_filter import normalize_selected_tool_names

__all__ = (
    "build_agent_tool_context_json",
    "build_agent_tool_hints_text",
)


class _AgentToolContextFields(TypedDict):
    version: int
    agent_mode: str
    tools: list[JSONDict]
    profiles: JSONDict


def _format_tool_names(tool_names: tuple[str, ...]) -> str:
    if len(tool_names) == 1:
        return tool_names[0]
    if len(tool_names) == 2:
        return f"{tool_names[0]} or {tool_names[1]}"
    return ", ".join(tool_names[:-1]) + f", or {tool_names[-1]}"


def _available_tool_names(
    decoded_names: frozenset[str] | set[str],
    *tool_names: str,
) -> tuple[str, ...]:
    return tuple(tool_name for tool_name in tool_names if tool_name in decoded_names)


def build_agent_tool_context_json(
    *,
    agent_mode: str,
    tool_names: list[str],
    tool_entries: dict[str, JSONDict],
) -> str:
    normalized_mode = normalize_agent_mode(agent_mode, strict=False)
    normalized_names = [str(name or "").strip() for name in tool_names if str(name or "").strip()]
    tools = build_tool_payload_entries(tool_names=normalized_names, tool_entries=tool_entries)
    payload: _AgentToolContextFields = {
        "version": 1,
        "agent_mode": normalized_mode,
        "tools": tools,
        "profiles": collect_profiles_from_tool_payloads(tools),
    }
    return serialize_json_compact_stable_strict(
        filter_json_mapping_strict(
            payload,
            error_message="Agent tool context payload must be JSON-compatible.",
        ),
        ensure_ascii=False,
    )


def build_agent_tool_hints_text(
    *,
    agent_mode: str,
    tool_names: list[str],
    tool_entries: dict[str, JSONDict],
) -> str:
    normalized_mode = normalize_agent_mode(agent_mode, strict=False)
    normalized_names = [str(name or "").strip() for name in tool_names if str(name or "").strip()]
    tools = build_tool_payload_entries(tool_names=normalized_names, tool_entries=tool_entries)
    categories = {str(tool.get("category")) for tool in tools}
    decoded_names = normalize_selected_tool_names(tuple(normalized_names))
    has_remote_tools = any(str(tool.get("source")) != "local" for tool in tools)
    lines: list[str] = []
    lines.append(get_text_prompt_v1("agent.tool_hints.base.use_only_listed_tools.v1"))
    lines.append(get_text_prompt_v1("agent.tool_hints.base.unexpected_content.v1"))
    if "web" in categories or "browser" in categories:
        lines.append(get_text_prompt_v1("agent.tool_hints.web_live_facts.v1"))
    if normalized_mode == "plan":
        lines.append(get_text_prompt_v1("agent.tool_hints.plan_mode.no_destructive.v1"))
        if "plan_write" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.plan_mode.use_plan_write.v1"))
    if "apply_patch" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.edits.prefer_apply_patch.v1"))
    if "read_file" in decoded_names and bool(
        decoded_names & {"apply_patch", "replace_in_file", "write_file"},
    ):
        lines.append(get_text_prompt_v1("agent.tool_hints.edits.read_before_write.v1"))
    if "shell" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.shell.use_shell.v1"))
        if "shell_output_read" in decoded_names or "shell_output_search" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.shell.read_paginated_output.v1"))
        lines.append(get_text_prompt_v1("agent.tool_hints.shell.git_if_available.v1"))
    if "read_image" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.images.read_image.v1"))
    if "read_video" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.video.read_video.v1"))
    if "read_document" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.documents.read_document_continue.v1"))
    if "browser" in categories:
        if "browser_navigate" in decoded_names and "browser_snapshot" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.start_with_snapshot.v1"))
        browser_navigation_tools = _available_tool_names(decoded_names, "browser_navigate")
        if "browser_snapshot" in decoded_names and browser_navigation_tools:
            lines.append(
                render_text_prompt_template_v1(
                    "agent.tool_hints.browser.include_snapshot_hint_template.v1",
                    {"BROWSER_NAVIGATION_TOOLS": _format_tool_names(browser_navigation_tools)},
                ),
            )
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.refresh_refs.v1"))
        browser_interaction_tools = _available_tool_names(
            decoded_names,
            "browser_click",
            "browser_type",
        )
        if "browser_snapshot" in decoded_names and browser_interaction_tools:
            lines.append(
                render_text_prompt_template_v1(
                    "agent.tool_hints.browser.url_changed_refresh_template.v1",
                    {"BROWSER_INTERACTION_TOOLS": _format_tool_names(browser_interaction_tools)},
                ),
            )
        lines.append(get_text_prompt_v1("agent.tool_hints.browser.session_isolation.v1"))
        lines.append(get_text_prompt_v1("agent.tool_hints.browser.persistence_modes.v1"))
        if "browser_profiles" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.use_profiles_tool.v1"))
        if "browser_status" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.use_status_tool.v1"))
        if "browser_snapshot" in decoded_names:
            lines.append(
                get_text_prompt_v1("agent.tool_hints.browser.truncated_snapshot_continue.v1"),
            )
        if "browser_dialog" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.check_dialogs.v1"))
        if "browser_close" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.close_recovery.v1"))
        if "browser_persistence_reset" in decoded_names:
            lines.append(
                get_text_prompt_v1("agent.tool_hints.browser.persistence_reset_recovery.v1"),
            )
        if "browser_tabs" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.tabs_tool.v1"))
        if "browser_downloads" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.downloads_tool.v1"))
        if "browser_console" in decoded_names and "browser_network" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.console_or_network.v1"))
        if "browser_console" in decoded_names and "browser_network" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.console_network_filters.v1"))
        if "browser_pdf" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.pdf_tool.v1"))
        if "browser_resize" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.resize_tool.v1"))
        if "browser_eval" in decoded_names:
            lines.append(get_text_prompt_v1("agent.tool_hints.browser.eval_disabled_hint.v1"))
        autofill_tools = _available_tool_names(
            decoded_names,
            "browser_autofill_vault",
            "browser_autofill_secret",
        )
        if autofill_tools:
            lines.append(
                render_text_prompt_template_v1(
                    "agent.tool_hints.browser.autofill_prefer_template.v1",
                    {"BROWSER_AUTOFILL_TOOLS": _format_tool_names(autofill_tools)},
                ),
            )
    if "ask_user" in categories:
        lines.append(get_text_prompt_v1("agent.tool_hints.ask_user.must_use_tool.v1"))
        vault_secret_request_tools = _available_tool_names(
            decoded_names,
            "vault_secret_request",
            "vault_login_request",
        )
        if vault_secret_request_tools:
            lines.append(
                render_text_prompt_template_v1(
                    "agent.tool_hints.ask_user.is_secret_rules_template.v1",
                    {"SECURE_HANDLE_TOOLS": _format_tool_names(vault_secret_request_tools)},
                ),
            )
        lines.append(get_text_prompt_v1("agent.tool_hints.ask_user.minimum_needed.v1"))
        if normalized_mode == "execute":
            lines.append(get_text_prompt_v1("agent.tool_hints.ask_user.execute_checkpoints.v1"))
    credential_lookup_tools = _available_tool_names(decoded_names, "vault_search", "vault_list")
    if credential_lookup_tools:
        lines.append(
            render_text_prompt_template_v1(
                "agent.tool_hints.credentials.check_vault_first_template.v1",
                {"CREDENTIAL_LOOKUP_TOOLS": _format_tool_names(credential_lookup_tools)},
            ),
        )
    secure_handle_tools = _available_tool_names(
        decoded_names,
        "vault_login_request",
        "vault_secret_request",
    )
    if secure_handle_tools:
        lines.append(
            render_text_prompt_template_v1(
                "agent.tool_hints.credentials.use_secure_handle_tools_template.v1",
                {"SECURE_HANDLE_TOOLS": _format_tool_names(secure_handle_tools)},
            ),
        )
    if "todo_write" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.planning.todo_write_consistency.v1"))
    if "notify_user" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.notify_user.v1"))
    if "automation_run_wait" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.automation.run_wait.v1"))
    memory_lookup_tools = _available_tool_names(
        decoded_names,
        "memory_conversation_history",
        "memory_search",
        "memory_recall",
    )
    if memory_lookup_tools:
        lines.append(
            render_text_prompt_template_v1(
                "agent.tool_hints.memory.use_history_search_template.v1",
                {"MEMORY_LOOKUP_TOOLS": _format_tool_names(memory_lookup_tools)},
            ),
        )
    if "memory_store" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.memory.store_durable.v1"))
        lines.append(get_text_prompt_v1("agent.tool_hints.memory.avoid_secrets.v1"))
    if "wait" in decoded_names:
        lines.append(get_text_prompt_v1("agent.tool_hints.wait_tool.v1"))
    if has_remote_tools:
        lines.append(get_text_prompt_v1("agent.tool_hints.remote_tools.respect_source.v1"))
    return "\n".join(lines).strip()
