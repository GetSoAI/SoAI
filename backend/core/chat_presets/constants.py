"""SoAI - Chat preset V1 field catalog and limits [backend/core/chat_presets/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.iteration_limits import MAX_AGENT_MAX_ITERATIONS
from core.rag.config_values import RAG_CONFIG_VALUE_FIELDS
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

__all__ = (
    "CHAT_PRESET_APPEARANCE_FIELDS",
    "CHAT_PRESET_COMPLETION_FIELDS",
    "CHAT_PRESET_FILES_FIELDS",
    "CHAT_PRESET_GENERAL_FIELDS",
    "CHAT_PRESET_KNOWLEDGE_FIELDS",
    "CHAT_PRESET_MAX_AGENT_ITERATIONS",
    "CHAT_PRESET_MAX_NAME_CODE_POINTS",
    "CHAT_PRESET_MAX_SECTIONS_JSON_BYTES",
    "CHAT_PRESET_MAX_STOP_ENTRIES",
    "CHAT_PRESET_MOBILE_AUXILIARY_ACTIONS",
    "CHAT_PRESET_REASONING_EFFORTS",
    "CHAT_PRESET_SECTION_IDS",
    "CHAT_PRESET_SERVICE_TIERS",
    "CHAT_PRESET_TOOL_MODES",
    "CHAT_PRESET_TOOLS_FIELDS",
    "CHAT_PRESET_VOICE_FIELDS",
    "JAVASCRIPT_SAFE_INTEGER_MAX",
    "chat_preset_section_fields",
)

CHAT_PRESET_MAX_NAME_CODE_POINTS = 255
CHAT_PRESET_MAX_SECTIONS_JSON_BYTES = 65_536
CHAT_PRESET_MAX_STOP_ENTRIES = 50
CHAT_PRESET_MAX_AGENT_ITERATIONS = MAX_AGENT_MAX_ITERATIONS

CHAT_PRESET_GENERAL_FIELDS = frozenset(
    {
        "model",
        "user_display_name",
        "assistant_display_name",
        "hide_real_model",
        "conversation_pdf_export_enabled",
        "new_conversation_inherit_last_settings",
        "ctrl_enter_send_enabled",
    },
)
CHAT_PRESET_APPEARANCE_FIELDS = frozenset(
    {
        "text_zoom",
        "widescreen_mode",
        "rich_text_enabled",
        "inline_multimedia_previews_enabled",
        "auto_title_generation",
        "show_activities",
        "hide_automation_runs",
        "hide_messaging_conversations",
        "notify_on_completion",
        "notify_on_error",
        "microphone_sound_effects_enabled",
        "input_action_voice_enabled",
        "input_action_call_enabled",
        "input_action_file_upload_enabled",
        "input_action_camera_enabled",
        "input_action_prompts_enabled",
        "input_action_token_counter_enabled",
        "input_action_new_conversation_enabled",
        "input_action_character_map_enabled",
        "input_action_mobile_auxiliary_action",
    },
)
CHAT_PRESET_COMPLETION_FIELDS = frozenset(
    {
        "user_system_prompt",
        "user_system_prompt_lock_enabled",
        "soai_system_prompt_enabled",
        "context_window_tokens",
        "reasoning_effort",
        "reasoning_effort_send_enabled",
        "max_completion_tokens",
        "max_completion_tokens_send_enabled",
        "agent_max_iterations",
        "temperature",
        "top_p",
        "top_p_send_enabled",
        "frequency_penalty",
        "frequency_penalty_send_enabled",
        "presence_penalty",
        "presence_penalty_send_enabled",
        "stop",
        "stop_send_enabled",
        "top_logprobs",
        "logprobs_send_enabled",
        "service_tier",
    },
)
CHAT_PRESET_VOICE_FIELDS = frozenset({"voice_tts_model", "voice_stt_model"})
CHAT_PRESET_KNOWLEDGE_FIELDS = RAG_CONFIG_VALUE_FIELDS
CHAT_PRESET_FILES_FIELDS = frozenset({"workspace_path"})
CHAT_PRESET_TOOLS_FIELDS = frozenset(
    {"tools_enabled", "tool_approval_required", "servers", "modes"}
)
CHAT_PRESET_SECTION_IDS = (
    "general",
    "appearance",
    "completion",
    "voice",
    "files",
    "knowledge",
    "tools",
)
CHAT_PRESET_TOOL_MODES = frozenset({"default", "plan", "execute"})
CHAT_PRESET_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max"},
)
CHAT_PRESET_SERVICE_TIERS = frozenset({"auto", "default", "flex", "priority"})
CHAT_PRESET_MOBILE_AUXILIARY_ACTIONS = frozenset(
    {
        "none",
        "agent_mode",
        "agent_compact",
        "export",
        "configuration",
        "favorite",
        "tools",
        "token_counter",
        "voice",
        "voice_call",
        "camera",
        "attach",
        "prompts",
        "character_map",
        "new_conversation",
    },
)


def chat_preset_section_fields(section: str) -> frozenset[str] | None:
    if section == "general":
        return CHAT_PRESET_GENERAL_FIELDS
    if section == "appearance":
        return CHAT_PRESET_APPEARANCE_FIELDS
    if section == "completion":
        return CHAT_PRESET_COMPLETION_FIELDS
    if section == "voice":
        return CHAT_PRESET_VOICE_FIELDS
    if section == "files":
        return CHAT_PRESET_FILES_FIELDS
    if section == "knowledge":
        return CHAT_PRESET_KNOWLEDGE_FIELDS
    if section == "tools":
        return CHAT_PRESET_TOOLS_FIELDS
    return None
