"""SoAI - System prompt catalog loading [backend/core/prompts/system_prompts_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.prompts.system_prompts_schema import (
    ModeTemplatePromptEntryV1,
    SystemPromptEntryV1,
    SystemPromptsPayloadV1,
    SystemPromptTemplateEntryV1,
    TextPromptEntryV1,
    TextPromptTemplateEntryV1,
    load_system_prompts_payload_v1,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = (
    "SystemPromptTemplate",
    "SystemPromptsCatalog",
    "TextPromptTemplate",
    "load_system_prompts_catalog",
)

_SOAI_SYSTEM_PROMPT_ID: str = "soai.system.v1"
_SOAI_POLICY_PROMPT_ID_ENTRIES: tuple[tuple[str, str], ...] = (
    ("browser_core", "soai.policy.browser_core.v1"),
    ("browser_planning", "soai.policy.browser_planning.v1"),
    ("browser_accounts", "soai.policy.browser_accounts.v1"),
    ("browser_commerce", "soai.policy.browser_commerce.v1"),
    ("browser_recovery", "soai.policy.browser_recovery.v1"),
    ("credentials", "soai.policy.credentials.v1"),
    ("execution_completion", "soai.policy.execution_completion.v1"),
    ("ambiguity_and_reversibility", "soai.policy.ambiguity_and_reversibility.v1"),
    ("failure_strategy", "soai.policy.failure_strategy.v1"),
    ("user_progress_and_reporting", "soai.policy.user_progress_and_reporting.v1"),
    ("long_running_workflows", "soai.policy.long_running_workflows.v1"),
    ("verification_and_observation", "soai.policy.verification_and_observation.v1"),
    ("multi_context_coordination", "soai.policy.multi_context_coordination.v1"),
    ("manual_checkpoint_handling", "soai.policy.manual_checkpoint_handling.v1"),
    ("unsupported_and_fallbacks", "soai.policy.unsupported_and_fallbacks.v1"),
    ("authoring_and_outbound_content", "soai.policy.authoring_and_outbound_content.v1"),
    ("mail_calendar_mcp", "soai.policy.mail_calendar_mcp.v1"),
    ("coding", "soai.policy.coding.v1"),
    ("research", "soai.policy.research.v1"),
    ("memory_automation", "soai.policy.memory_automation.v1"),
    ("subagents", "soai.policy.subagents.v1"),
    ("automation", "soai.policy.automation.v1"),
)
_COMPACTION_SUMMARY_ID: str = "openai.compaction.summary.v1"
_AGENT_COMPACTION_SUMMARY_ID: str = "openai.compaction.summary.agent.v1"
_REQUIRED_TOOL_CALL_ID: str = "agent.required_tool_call.v1"
_REQUIRED_VISIBLE_OUTPUT_ID: str = "agent.required_visible_output.v1"
_AGENT_MODE_PROMPT_ID_ENTRIES: tuple[tuple[str, str], ...] = (
    ("chat", "agent.mode.chat.v1"),
    ("plan", "agent.mode.plan.v1"),
    ("execute", "agent.mode.execute.v1"),
)


@dataclass(frozen=True, slots=True)
class SystemPromptTemplate:
    marker: str
    template: str
    placeholders: tuple[str, ...]

    def render(self, mapping: Mapping[str, str]) -> str:
        try:
            return self.template.format_map(mapping)
        except KeyError as exception:
            raise ValidationError(f"Missing system prompt placeholder: {exception}") from exception


@dataclass(frozen=True, slots=True)
class TextPromptTemplate:
    template: str
    placeholders: tuple[str, ...]

    def render(self, mapping: Mapping[str, str]) -> str:
        try:
            return self.template.format_map(mapping)
        except KeyError as exception:
            raise ValidationError(f"Missing prompt placeholder: {exception}") from exception


@dataclass(frozen=True, slots=True)
class SystemPromptsCatalog:
    soai_system_prompt_v1: SystemPromptTemplate
    soai_policy_templates_v1: dict[str, str]
    compaction_summary_system_text_v1: str
    agent_compaction_summary_system_text_v1: str
    required_tool_call_system_text_v1: str
    required_visible_output_system_text_v1: str
    agent_mode_templates_v1: dict[str, str]
    text_prompts_v1: dict[str, str]
    text_prompt_templates_v1: dict[str, TextPromptTemplate]


def _require_prompt_entry(
    payload: SystemPromptsPayloadV1,
    prompt_id: str,
) -> (
    SystemPromptTemplateEntryV1
    | TextPromptTemplateEntryV1
    | ModeTemplatePromptEntryV1
    | SystemPromptEntryV1
    | TextPromptEntryV1
):
    entry = payload.prompts.get(prompt_id)
    if entry is None:
        raise ValidationError(f"Missing prompt entry: {prompt_id}")
    return entry


def _require_prompt_entry_type(
    payload: SystemPromptsPayloadV1,
    prompt_id: str,
    expected_type: str,
) -> (
    SystemPromptTemplateEntryV1
    | TextPromptTemplateEntryV1
    | ModeTemplatePromptEntryV1
    | SystemPromptEntryV1
    | TextPromptEntryV1
):
    entry = _require_prompt_entry(payload, prompt_id)
    if entry.type != expected_type:
        raise ValidationError(f"prompt:{prompt_id}.type must be {expected_type!r}.")
    return entry


def _read_required_system_text(payload: SystemPromptsPayloadV1, prompt_id: str) -> str:
    entry = _require_prompt_entry_type(payload, prompt_id, "system")
    if not isinstance(entry, SystemPromptEntryV1):
        raise ValidationError("Invalid system prompt entry.")
    return entry.content


def _read_mode_templates(payload: SystemPromptsPayloadV1) -> dict[str, str]:
    templates: dict[str, str] = {}
    for mode, prompt_id in _AGENT_MODE_PROMPT_ID_ENTRIES:
        entry = _require_prompt_entry_type(payload, prompt_id, "mode_template")
        if not isinstance(entry, ModeTemplatePromptEntryV1):
            raise ValidationError("Invalid mode template entry.")
        templates[mode] = entry.content
    return templates


def _read_policy_templates(payload: SystemPromptsPayloadV1) -> dict[str, str]:
    templates: dict[str, str] = {}
    for policy_name, prompt_id in _SOAI_POLICY_PROMPT_ID_ENTRIES:
        templates[policy_name] = _read_required_system_text(payload, prompt_id)
    return templates


def _read_text_prompts_and_templates(
    payload: SystemPromptsPayloadV1,
) -> tuple[dict[str, str], dict[str, TextPromptTemplate]]:
    text_prompts: dict[str, str] = {}
    text_templates: dict[str, TextPromptTemplate] = {}
    for prompt_id, entry in payload.prompts.items():
        if not prompt_id.strip():
            raise ValidationError("Prompt id keys must be non-empty strings.")
        if entry.type == "system":
            if not isinstance(entry, SystemPromptEntryV1):
                raise ValidationError("Invalid system prompt entry.")
            text_prompts[prompt_id] = entry.content
            continue
        if entry.type == "text":
            if not isinstance(entry, TextPromptEntryV1):
                raise ValidationError("Invalid text prompt entry.")
            text_prompts[prompt_id] = entry.content
            continue
        if entry.type == "text_template":
            if not isinstance(entry, TextPromptTemplateEntryV1):
                raise ValidationError("Invalid text template entry.")
            text_templates[prompt_id] = TextPromptTemplate(
                template=entry.template,
                placeholders=entry.placeholders,
            )
            continue
        if entry.type in {"system_template", "mode_template"}:
            continue
        raise ValidationError(f"Unsupported prompt type: {entry.type!r}.")
    return (text_prompts, text_templates)


@lru_cache(maxsize=1)
def load_system_prompts_catalog() -> SystemPromptsCatalog:
    payload = load_system_prompts_payload_v1()
    soai_entry = _require_prompt_entry_type(payload, _SOAI_SYSTEM_PROMPT_ID, "system_template")
    if not isinstance(soai_entry, SystemPromptTemplateEntryV1):
        raise ValidationError("Invalid SoAI system prompt template entry.")
    text_prompts, text_templates = _read_text_prompts_and_templates(payload)
    return SystemPromptsCatalog(
        soai_system_prompt_v1=SystemPromptTemplate(
            marker=soai_entry.marker,
            template=soai_entry.template,
            placeholders=soai_entry.placeholders,
        ),
        soai_policy_templates_v1=_read_policy_templates(payload),
        compaction_summary_system_text_v1=_read_required_system_text(
            payload,
            _COMPACTION_SUMMARY_ID,
        ),
        agent_compaction_summary_system_text_v1=_read_required_system_text(
            payload,
            _AGENT_COMPACTION_SUMMARY_ID,
        ),
        required_tool_call_system_text_v1=_read_required_system_text(
            payload,
            _REQUIRED_TOOL_CALL_ID,
        ),
        required_visible_output_system_text_v1=_read_required_system_text(
            payload,
            _REQUIRED_VISIBLE_OUTPUT_ID,
        ),
        agent_mode_templates_v1=_read_mode_templates(payload),
        text_prompts_v1=text_prompts,
        text_prompt_templates_v1=text_templates,
    )
