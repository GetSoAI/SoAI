"""SoAI - Agent capability policy selection [backend/features/agent/runtime/capability_policy_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent_mode import normalize_agent_mode
from core.prompts.system_prompts import get_soai_policy_template_v1
from core.types.json import JSONDict
from features.agent.runtime.tool_prompt_filter import (
    filter_prompt_lines_by_selected_tools,
    normalize_selected_tool_names,
)

__all__ = ("build_agent_capability_policies_text",)

_BROWSER_CORE_POLICY_TOOLS: frozenset[str] = frozenset(
    ("browser_navigate", "browser_snapshot", "web_fetch", "http_request"),
)
_BROWSER_RECOVERY_POLICY_TOOLS: frozenset[str] = frozenset(
    (
        "browser_status",
        "browser_dialog",
        "browser_tabs",
        "browser_downloads",
        "browser_console",
        "browser_network",
        "browser_profiles",
    ),
)
_CREDENTIAL_POLICY_TOOLS: frozenset[str] = frozenset(
    (
        "vault_search",
        "vault_list",
        "vault_login_request",
        "vault_secret_request",
        "browser_autofill_secret",
        "browser_autofill_vault",
    ),
)
_SUBAGENT_POLICY_TOOLS: frozenset[str] = frozenset(
    ("subagent_spawn", "subagent_observe", "subagent_cancel"),
)
_AUTOMATION_POLICY_TOOLS: frozenset[str] = frozenset(
    (
        "automation_create",
        "automation_run_enqueue",
        "automation_run_get",
        "automation_run_wait",
    ),
)
_MAIL_CALENDAR_POLICY_TOOLS: frozenset[str] = frozenset(
    (
        "mail_account_sync",
        "calendar_account_sync",
        "calendar_window_sync",
        "mail_messages_list",
        "mail_folders_list",
        "calendar_events_list",
        "calendar_calendars_list",
        "mail_messages_remote_search",
        "mail_folder_backfill",
        "mail_message_compose",
    ),
)


def _profile_is_enabled(profiles: JSONDict, profile_name: str) -> bool:
    return bool(profiles.get(profile_name))


def _policy_tools_available(
    *,
    selected_tools: frozenset[str],
    required_tools: frozenset[str],
    has_tool_selection: bool,
) -> bool:
    return not has_tool_selection or required_tools.issubset(selected_tools)


def _select_execute_policies(
    *,
    profiles: JSONDict,
    selected_tools: frozenset[str],
    has_tool_selection: bool,
) -> list[str]:
    selected_policies: list[str] = []
    can_execute_work = bool(
        _profile_is_enabled(profiles, "local_execution")
        or _profile_is_enabled(profiles, "external_effects")
        or _profile_is_enabled(profiles, "live_research")
        or _profile_is_enabled(profiles, "background_workflows")
        or _profile_is_enabled(profiles, "automation"),
    )
    if can_execute_work:
        selected_policies.append(get_soai_policy_template_v1("execution_completion"))
        selected_policies.append(get_soai_policy_template_v1("failure_strategy"))
        selected_policies.append(get_soai_policy_template_v1("user_progress_and_reporting"))
        selected_policies.append(get_soai_policy_template_v1("unsupported_and_fallbacks"))
    if can_execute_work or _profile_is_enabled(profiles, "external_effects"):
        selected_policies.append(get_soai_policy_template_v1("ambiguity_and_reversibility"))
    if can_execute_work and _profile_is_enabled(profiles, "verification_surface"):
        selected_policies.append(get_soai_policy_template_v1("verification_and_observation"))
    if can_execute_work and _profile_is_enabled(profiles, "interactive_checkpointing"):
        selected_policies.append(get_soai_policy_template_v1("manual_checkpoint_handling"))
    if can_execute_work and _profile_is_enabled(profiles, "authoring"):
        selected_policies.append(get_soai_policy_template_v1("authoring_and_outbound_content"))
    if _profile_is_enabled(profiles, "mail_calendar_mcp") and _policy_tools_available(
        selected_tools=selected_tools,
        required_tools=_MAIL_CALENDAR_POLICY_TOOLS,
        has_tool_selection=has_tool_selection,
    ):
        selected_policies.append(get_soai_policy_template_v1("mail_calendar_mcp"))
    if _profile_is_enabled(profiles, "session_coordination"):
        selected_policies.append(get_soai_policy_template_v1("multi_context_coordination"))
    if _profile_is_enabled(profiles, "background_workflows"):
        selected_policies.append(get_soai_policy_template_v1("long_running_workflows"))
    return selected_policies


def build_agent_capability_policies_text(
    *,
    agent_mode: str,
    profiles: JSONDict,
    tool_names: list[str] | tuple[str, ...] = (),
) -> str:
    selected_policies: list[str] = []
    normalized_mode = normalize_agent_mode(agent_mode, strict=False)
    selected_tools = normalize_selected_tool_names(tool_names)
    has_tool_selection = bool(tool_names)
    if normalized_mode == "execute":
        selected_policies.extend(
            _select_execute_policies(
                profiles=profiles,
                selected_tools=selected_tools,
                has_tool_selection=has_tool_selection,
            ),
        )
    if _profile_is_enabled(profiles, "browser") and normalized_mode == "plan":
        selected_policies.append(get_soai_policy_template_v1("browser_planning"))
    if (
        _profile_is_enabled(profiles, "browser")
        and normalized_mode != "plan"
        and _policy_tools_available(
            selected_tools=selected_tools,
            required_tools=_BROWSER_CORE_POLICY_TOOLS,
            has_tool_selection=has_tool_selection,
        )
    ):
        selected_policies.append(get_soai_policy_template_v1("browser_core"))
        selected_policies.append(get_soai_policy_template_v1("browser_accounts"))
        selected_policies.append(get_soai_policy_template_v1("browser_commerce"))
    if _profile_is_enabled(profiles, "browser_recovery") and _policy_tools_available(
        selected_tools=selected_tools,
        required_tools=_BROWSER_RECOVERY_POLICY_TOOLS,
        has_tool_selection=has_tool_selection,
    ):
        selected_policies.append(get_soai_policy_template_v1("browser_recovery"))
    if (
        _profile_is_enabled(profiles, "credentials")
        and normalized_mode != "plan"
        and _policy_tools_available(
            selected_tools=selected_tools,
            required_tools=_CREDENTIAL_POLICY_TOOLS,
            has_tool_selection=has_tool_selection,
        )
    ):
        selected_policies.append(get_soai_policy_template_v1("credentials"))
    if _profile_is_enabled(profiles, "local_execution"):
        selected_policies.append(get_soai_policy_template_v1("coding"))
    if _profile_is_enabled(profiles, "live_research"):
        selected_policies.append(get_soai_policy_template_v1("research"))
    if _profile_is_enabled(profiles, "memory") or _profile_is_enabled(profiles, "automation"):
        selected_policies.append(get_soai_policy_template_v1("memory_automation"))
    if _profile_is_enabled(profiles, "subagents") and _policy_tools_available(
        selected_tools=selected_tools,
        required_tools=_SUBAGENT_POLICY_TOOLS,
        has_tool_selection=has_tool_selection,
    ):
        selected_policies.append(get_soai_policy_template_v1("subagents"))
    if _profile_is_enabled(profiles, "automation") and _policy_tools_available(
        selected_tools=selected_tools,
        required_tools=_AUTOMATION_POLICY_TOOLS,
        has_tool_selection=has_tool_selection,
    ):
        selected_policies.append(get_soai_policy_template_v1("automation"))
    content = "\n\n".join(policy for policy in selected_policies if policy.strip()).strip()
    if not tool_names:
        return content
    return filter_prompt_lines_by_selected_tools(
        text=content,
        selected_tools=selected_tools,
    )
