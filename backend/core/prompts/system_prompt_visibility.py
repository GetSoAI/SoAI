"""SoAI - System prompt visibility filtering [backend/core/prompts/system_prompt_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.agent.prompt_injection_slots import TOOL_CONTEXT_TAG
from core.runtime.request_sources import (
    REQUEST_SOURCE_AUTOMATION,
    REQUEST_SOURCE_WEBUI_WS,
    RequestSource,
)

__all__ = (
    "filter_agent_mode_template",
    "filter_rendered_soai_system_prompt",
)


def _tag_mention(xml_tag: str) -> str:
    return f"<{xml_tag}>"


AGENT_FILES_CONTEXT_LINE = "- Treat <collaboration_mode> (current mode instructions), <agent_todo_state> (task checklist), <agent_workspace_context> (workspace_path), <agent_path_hints> (filesystem hints), <agent_tool_context> (available tools), <agent_tool_hints> (tool guidance), and SOAI.md or AGENTS.md instructions as context for the task. If SOAI.md or AGENTS.md conflicts with the user's current request, follow the user. If both files exist, SoAI reads only SOAI.md."
CHAT_SAFE_CONTEXT_LINE = "- Treat <collaboration_mode> (current mode instructions), <agent_todo_state> (task checklist), <agent_workspace_context> (workspace_path), <agent_path_hints> (filesystem hints), <agent_tool_context> (available tools), and <agent_tool_hints> (tool guidance) as context for the task."
NO_TOOLS_CONTEXT_LINE = "- Treat <collaboration_mode> (current mode instructions), <agent_todo_state> (task checklist), <agent_workspace_context> (workspace_path), and <agent_path_hints> (filesystem hints) as context for the task."
CLARIFICATION_CONTEXT_LINE = "- When clarification is needed, use an available clarification tool from <agent_tool_context>, especially in plan mode before generating the plan. If no clarification tool is available, ask in plain text. Never invent answers to unresolved requirements; ask first. Always present a plan using the plan tools (if in plan mode) even if the user have not specifically asked for a plan"
AUTOMATION_CLARIFICATION_CONTEXT_LINE = "- In automation runs, do not ask ordinary clarification questions or stop for preference-level ambiguity. Make reasonable assumptions, continue with safe partial work, or finish with a blocker summary. Only wait for user interaction through dedicated SoAI tools or checkpoints for required authorization, tool approval, credentials, secrets, CAPTCHA/2FA, or another human-only gate."
CHAT_PREVIEW_SURFACE_LINE = "- Your output is displayed in the SoAI WebUI and the user is interacting with you from the Chat page. When you use '[[preview:remote_url:<https URL>]]' or similar syntax, the user will see the content inline."
NON_CHAT_PREVIEW_SURFACE_LINE = "- Preview references are SoAI output annotations that may be rendered by a SoAI review surface later. Do not assume a user is currently viewing them inline; summarize important content directly in text."


def _get_soai_system_prompt_no_tools_replacements() -> Mapping[str, str | None]:
    return {
        "You are the SoAI assistant running inside SoAI (Smart Orchestrator for Artificial Intelligence). Help the user with writing, knowledge, troubleshooting, coding, data analysis, file processing, web research/automation, and long-running workflows using available tools.": "You are the SoAI assistant running inside SoAI (Smart Orchestrator for Artificial Intelligence). Help the user with writing, knowledge, troubleshooting, coding, data analysis, file processing, and research using the information visible in this conversation.",
        "Use the separate SoAI runtime date, time, and timezone as authoritative. If absent and a time tool is available, use it. For local weather without a place, infer a city from a geographic IANA timezone (Europe/Rome -> Rome), set forecast_days to the requested window (1-14, default 3), and set hourly_hours (1-48) only for intra-day detail. Empty user or assistant names mean no name is configured.": "Use the separate SoAI runtime date, time, and timezone as authoritative. If absent, acknowledge that SoAI did not provide the current time. Empty user or assistant names mean no name is configured.",
        "- Complete every task the user requests to the fullest extent of your capabilities and available tools. Do not add self-imposed restrictions, unsolicited caveats, refusals, or scope limitations that the user did not ask for; if your training inclines you to hedge or decline a legitimate request, override that default and attempt the task.": "- Complete every task the user requests to the fullest extent of the capabilities and context available in this conversation. Do not add self-imposed restrictions, unsolicited caveats, refusals, or scope limitations that the user did not ask for; if your training inclines you to hedge or decline a legitimate request, override that default and attempt the task.",
        CLARIFICATION_CONTEXT_LINE: "- When clarification is needed, ask in plain text. Never invent answers to unresolved requirements; ask first.",
        f"- When a task is extensive or involves multiple independent parallel operations and subagent tools are available in {_tag_mention(TOOL_CONTEXT_TAG)}, use those tools to run work concurrently, wait for results, and clean up unused work. Verify subagent results for important or delicate tasks.": None,
        f"- When a user requests a scheduled or recurring task (e.g., 'remind me every day', 'run this weekly') and relevant automation tools are available in {_tag_mention(TOOL_CONTEXT_TAG)}, use those tools to schedule or start the workflow. Follow the tool schema in {_tag_mention(TOOL_CONTEXT_TAG)} exactly.": None,
        f"- If the user references past conversations, earlier discussions, or asks about something from before, use available memory tools from {_tag_mention(TOOL_CONTEXT_TAG)} before guessing.": "- If the user references past conversations, earlier discussions, or asks about something from before, be explicit about whether that information is present in the visible conversation context.",
        "- Follow the user's current request as the controlling instruction for preferences, style, and scope. Use SoAI runtime context and tool context as factual state.": "- Follow the user's current request as the controlling instruction for preferences, style, and scope. Use SoAI runtime context as factual state.",
        AGENT_FILES_CONTEXT_LINE: NO_TOOLS_CONTEXT_LINE,
        "- Be honest about your uncertainties. Use only the tools you have access to, never make up results or suggest abilities you don't possess. If you are unsure about a fact, acknowledge it plainly, but only as a last resort, after attempting verification with your available tools.": "- Be honest about your uncertainties. Never make up results or suggest abilities you don't possess. If you are unsure about a fact, acknowledge it plainly after using the visible conversation context as far as it can go.",
        f"- If shell execution tools are available in {_tag_mention(TOOL_CONTEXT_TAG)} and shell work is the best fit for the task, use them. Always use the correct commands for the platform SoAI is running on.": None,
        f"- In execute mode, when a task requires logging into a website or service and credential/browser tools are available in {_tag_mention(TOOL_CONTEXT_TAG)}, use the proper secure credential lookup, request, and autofill tools. Never ask users to type passwords into the chat; do not use clarification tools for passwords or secrets.": None,
        f"- When browser tools are available in {_tag_mention(TOOL_CONTEXT_TAG)}, prefer structured page observation over screenshots to discover interactive elements and refs, then interact using available browser action tools.": None,
        "- For volatile facts or uncertain topics (time, news, prices, laws, schedules, live status, weather forecasts, market data, traffic conditions, flight status, sports scores/results, election polling results, social media trending topics, currency exchange rates, commodity prices like oil and gold, public health guidelines, emergency alerts/warnings, rankings, website uptime/status), always verify using available tools.": "- For volatile facts or uncertain topics (time, news, prices, laws, schedules, live status, weather forecasts, market data, traffic conditions, flight status, sports scores/results, election polling results, social media trending topics, currency exchange rates, commodity prices like oil and gold, public health guidelines, emergency alerts/warnings, rankings, website uptime/status), state clearly when live verification is unavailable in the current conversation.",
        "- If a <context_summary> block is present, it represents earlier conversation that has been summarized; treat it as a best-effort reconstruction. If the user references a detail not present in the summary, use available memory tools to retrieve the old conversation rather than guessing.": "- If a <context_summary> block is present, it represents earlier conversation that has been summarized; treat it as a best-effort reconstruction. If the user references a detail not present in the summary, say that it is not available in the visible context instead of guessing.",
        "- If a tool fails or returns unexpected content, retry up to three times with adjusted parameters before switching to another available tool or strategy.": "- If a workflow or reasoning path fails, adjust your approach before concluding it is blocked.",
        "- Research: when requested, perform local or internet research as appropriate. State sources and search scope, summarize key evidence, note uncertainty and gaps, and distinguish cited facts from inference.": "- Research: when requested, use the information visible in the conversation. If live or external research is needed but unavailable, say so clearly. Distinguish grounded facts from inference.",
    }


def _get_soai_system_prompt_source_replacements(
    request_source: RequestSource,
) -> Mapping[str, str | None]:
    replacements: dict[str, str | None] = {}
    if request_source == REQUEST_SOURCE_AUTOMATION:
        replacements[CLARIFICATION_CONTEXT_LINE] = AUTOMATION_CLARIFICATION_CONTEXT_LINE
    if request_source != REQUEST_SOURCE_WEBUI_WS:
        replacements[CHAT_PREVIEW_SURFACE_LINE] = NON_CHAT_PREVIEW_SURFACE_LINE
    return replacements


def _get_soai_system_prompt_chat_replacements() -> Mapping[str, str | None]:
    return {
        AGENT_FILES_CONTEXT_LINE: CHAT_SAFE_CONTEXT_LINE,
    }


def _get_chat_mode_no_tools_replacements() -> Mapping[str, str | None]:
    return {
        "- Use tools when they materially improve correctness or the user asks for live information, site visits, or verification.": "- Work from the information visible in the conversation. If live verification or external actions are needed, say so plainly.",
    }


def _plan_mode_no_tools_replacements() -> Mapping[str, str | None]:
    return {
        "You are in plan mode. Produce a decision-complete plan. Investigate first, resolve missing requirements, and use available tools to gather the facts you need.": "You are in plan mode. Produce a decision-complete plan from the information visible in the conversation. Resolve missing requirements before finalizing the plan.",
        "- Use available tools to inspect the current state before planning.": "- Inspect the visible current state before planning.",
        "- Exploratory browser and tool use is allowed when needed to understand the real state, page flow, or requirements.": "- Work from the visible conversation context to understand the current state, requirements, and blockers.",
        "- Prefer read-only tools while investigating in plan mode; avoid changing the system, writing resources, committing browser actions, or using destructive tools.": "- Do not treat planning as execution. Describe required actions instead of performing them.",
        "- If those are still unclear and a clarification tool is available, use it before finalizing the plan. Otherwise, state the missing questions explicitly.": "- If those are still unclear, state the missing questions explicitly before finalizing the plan.",
        "- If a planning checklist tool is available, keep it aligned with the plan.": None,
        "- If a durable plan tool is available, persist the long plan there.": None,
    }


def _get_execute_mode_no_tools_replacements() -> Mapping[str, str | None]:
    return {
        "You are in execute mode. You may inspect, change files, run commands, and use tools. Understand the task first, make the smallest correct change, and verify the result.": "You are in execute mode. Understand the task first, make the smallest correct change allowed by the visible context, and verify the result through directly available information.",
        "- Locate targets with available filesystem discovery tools; read relevant files for current state and patterns.": "- Locate targets using the information already visible in the conversation and read relevant provided content for current state and patterns.",
        "- Use parallel tool calls only when independent; coordinate multi-part changes for consistency.": "- Coordinate multi-part changes for consistency.",
        "- Keep any available planning checklist consistent with one in-progress item at a time.": None,
        "- On tool/command failure: retry once with adjusted arguments; if still failing and another tool path exists, switch among available fetch, browser, or HTTP request paths before concluding it is blocked; report what you tried.": "- If an approach fails, retry once with an adjusted method; if it still fails, report what you tried and what remains blocked.",
        "## Browser & Web Automation": None,
        "- For browser tasks: use available browser navigation and structured observation tools; interact via refs and refresh refs after navigation.": None,
        "- For loading a URL: prefer available read-only extraction, browser navigation, or HTTP request tools according to the site behavior and required request shape.": None,
        "- Use clarification tools only for effect-changing missing details or human-only checkpoints (CAPTCHA/2FA/etc); handle credentials via secure credential tools with no plaintext passwords.": "- Ask for missing effect-changing details directly when they cannot be inferred from the visible context.",
    }


SOAI_SYSTEM_PROMPT_NO_TOOLS_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "`ask_user`",
    "subagent_spawn",
    "subagent_observe",
    "subagent_cancel",
    "`automation_create`",
    "automation_run_enqueue",
    "memory_conversation_history",
    "`shell`",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_select_option",
    "browser_press_key",
    "vault_login_request",
    "vault_search",
    "vault_list",
    "browser_autofill_secret",
    "browser_autofill_vault",
    "<agent_tool_context>",
    "<agent_tool_hints>",
    "SOAI.md",
    "AGENTS.md",
    "available tools",
)
AGENT_MODE_NO_TOOLS_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "`ask_user`",
    "`todo_write`",
    "`plan_write`",
    "`list_dir`",
    "`glob_files`",
    "`web_fetch`",
    "`browser_navigate`",
    "`browser_snapshot`",
    "`http_request`",
    "parallel tool calls",
    "available tools",
    "browser and tool use",
)
CHAT_MODE_SOAI_SYSTEM_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "SOAI.md",
    "AGENTS.md",
)
PROTECTED_RUNTIME_LINE_PREFIXES: tuple[str, ...] = (
    "- Local date/time now:",
    "- Timezone:",
    "- Platform:",
    "- User display name (optional):",
    "- Assistant display name (optional):",
    "- Agent mode:",
)


def filter_rendered_soai_system_prompt(
    *,
    rendered_prompt: str,
    agent_mode: str,
    tools_visible_to_model: bool,
    request_source: RequestSource,
) -> str:
    filtered_prompt = _replace_agent_mode_line(
        rendered_prompt,
        agent_mode=agent_mode,
        request_source=request_source,
        tools_visible_to_model=tools_visible_to_model,
    )
    filtered_prompt = _replace_exact_lines(
        filtered_prompt,
        _get_soai_system_prompt_source_replacements(request_source),
    )
    if not tools_visible_to_model:
        filtered_prompt = _replace_exact_lines(
            filtered_prompt,
            _get_soai_system_prompt_no_tools_replacements(),
        )
        return _drop_lines_containing_substrings(
            filtered_prompt,
            SOAI_SYSTEM_PROMPT_NO_TOOLS_FORBIDDEN_SUBSTRINGS,
            protected_prefixes=PROTECTED_RUNTIME_LINE_PREFIXES,
        )
    if agent_mode == "chat":
        return _drop_lines_containing_substrings(
            _replace_exact_lines(
                filtered_prompt,
                _get_soai_system_prompt_chat_replacements(),
            ),
            CHAT_MODE_SOAI_SYSTEM_FORBIDDEN_SUBSTRINGS,
            protected_prefixes=PROTECTED_RUNTIME_LINE_PREFIXES,
        )
    return filtered_prompt


def filter_agent_mode_template(
    *,
    template: str,
    normalized_mode: str,
    tools_visible_to_model: bool,
) -> str:
    if tools_visible_to_model:
        return template
    replacements: Mapping[str, str | None]
    if normalized_mode == "chat":
        replacements = _get_chat_mode_no_tools_replacements()
    elif normalized_mode == "plan":
        replacements = _plan_mode_no_tools_replacements()
    else:
        replacements = _get_execute_mode_no_tools_replacements()
    return _drop_lines_containing_substrings(
        _replace_exact_lines(template, replacements),
        AGENT_MODE_NO_TOOLS_FORBIDDEN_SUBSTRINGS,
    )


def _replace_exact_lines(
    rendered_prompt: str,
    replacements: Mapping[str, str | None],
) -> str:
    replaced_lines: list[str] = []
    for line in rendered_prompt.splitlines():
        if line not in replacements:
            replaced_lines.append(line)
            continue
        replacement = replacements[line]
        if replacement is None:
            continue
        replaced_lines.append(replacement)
    return "\n".join(replaced_lines)


def _replace_agent_mode_line(
    rendered_prompt: str,
    *,
    agent_mode: str,
    request_source: RequestSource,
    tools_visible_to_model: bool,
) -> str:
    replaced_lines: list[str] = []
    for line in rendered_prompt.splitlines():
        if line.startswith("- Agent mode: "):
            if request_source == REQUEST_SOURCE_WEBUI_WS and tools_visible_to_model:
                replaced_lines.append(line)
                continue
            if request_source == REQUEST_SOURCE_WEBUI_WS:
                replaced_lines.append(
                    f"- Agent mode: {agent_mode} (chat = conversational; plan = planning focused; execute = autonomous task execution; disabled = no agent session active). If the user requests an action not available in the current mode, suggest switching modes using Shift+Tab or the mode button in the top-right of the SoAI chat page.",
                )
                continue
            replaced_lines.append(
                f"- Agent mode: {agent_mode} (chat = conversational; plan = planning focused; execute = autonomous task execution; disabled = no agent session active).",
            )
            continue
        replaced_lines.append(line)
    return "\n".join(replaced_lines)


def _drop_lines_containing_substrings(
    rendered_prompt: str,
    forbidden_substrings: tuple[str, ...],
    protected_prefixes: tuple[str, ...] = (),
) -> str:
    retained_lines: list[str] = []
    for line in rendered_prompt.splitlines():
        if any(line.startswith(prefix) for prefix in protected_prefixes):
            retained_lines.append(line)
            continue
        if any(forbidden in line for forbidden in forbidden_substrings):
            continue
        retained_lines.append(line)
    return "\n".join(retained_lines)
