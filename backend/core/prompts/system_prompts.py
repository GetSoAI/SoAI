"""SoAI - System prompt accessors [backend/core/prompts/system_prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from core.agent_mode import coerce_agent_mode_or_none
from core.errors.exceptions import ValidationError
from core.prompts.system_prompt_visibility import (
    filter_agent_mode_template,
    filter_rendered_soai_system_prompt,
)
from core.prompts.system_prompts_catalog import (
    SystemPromptsCatalog,
    SystemPromptTemplate,
    TextPromptTemplate,
    load_system_prompts_catalog,
)
from core.runtime.request_sources import RequestSource

__all__ = (
    "SystemPromptTemplate",
    "SystemPromptsCatalog",
    "TextPromptTemplate",
    "get_agent_compaction_summary_system_text_v1",
    "get_agent_mode_template_v1",
    "get_compaction_summary_system_text_v1",
    "get_required_tool_call_system_text_v1",
    "get_required_visible_output_system_text_v1",
    "get_soai_policy_template_v1",
    "get_soai_system_prompt_marker_v1",
    "get_soai_system_prompt_template_v1",
    "get_text_prompt_v1",
    "load_system_prompts_catalog",
    "render_soai_system_prompt_v1",
    "render_text_prompt_template_v1",
)


def get_soai_system_prompt_template_v1() -> str:
    return load_system_prompts_catalog().soai_system_prompt_v1.template


def get_soai_system_prompt_marker_v1() -> str:
    return load_system_prompts_catalog().soai_system_prompt_v1.marker


def render_soai_system_prompt_v1(
    *,
    platform_info: str,
    user_name: str,
    assistant_name: str,
    agent_mode: str,
    tools_visible_to_model: bool,
    request_source: RequestSource,
) -> str:
    rendered = load_system_prompts_catalog().soai_system_prompt_v1.render(
        {
            "SOAI_PLATFORM": str(platform_info),
            "SOAI_USER_NAME": str(user_name),
            "SOAI_ASSISTANT_NAME": str(assistant_name),
            "SOAI_AGENT_MODE": str(agent_mode),
        },
    )
    return filter_rendered_soai_system_prompt(
        rendered_prompt=rendered,
        agent_mode=agent_mode,
        tools_visible_to_model=tools_visible_to_model,
        request_source=request_source,
    )


def get_soai_policy_template_v1(policy_name: str) -> str:
    normalized_policy_name = str(policy_name).strip().lower()
    policy = load_system_prompts_catalog().soai_policy_templates_v1.get(normalized_policy_name)
    if policy is None:
        raise ValidationError("Unknown SoAI policy template.")
    return policy


def get_compaction_summary_system_text_v1() -> str:
    return load_system_prompts_catalog().compaction_summary_system_text_v1


def get_agent_compaction_summary_system_text_v1() -> str:
    return load_system_prompts_catalog().agent_compaction_summary_system_text_v1


def get_required_tool_call_system_text_v1() -> str:
    return load_system_prompts_catalog().required_tool_call_system_text_v1


def get_required_visible_output_system_text_v1() -> str:
    return load_system_prompts_catalog().required_visible_output_system_text_v1


def get_agent_mode_template_v1(
    mode: Literal["chat", "plan", "execute"] | str,
    *,
    tools_visible_to_model: bool,
) -> str:
    normalized_mode = coerce_agent_mode_or_none(mode)
    if normalized_mode is None:
        raise ValidationError("Unknown agent mode.")
    template = load_system_prompts_catalog().agent_mode_templates_v1.get(normalized_mode)
    if template is None:
        raise ValidationError("Unknown agent mode.")
    return filter_agent_mode_template(
        template=template,
        normalized_mode=normalized_mode,
        tools_visible_to_model=tools_visible_to_model,
    )


def get_text_prompt_v1(prompt_id: str) -> str:
    normalized = str(prompt_id or "").strip()
    if not normalized:
        raise ValidationError("prompt_id must be a non-empty string.")
    prompt = load_system_prompts_catalog().text_prompts_v1.get(normalized)
    if prompt is None:
        raise ValidationError("Unknown prompt id.")
    return prompt


def render_text_prompt_template_v1(prompt_id: str, mapping: Mapping[str, str]) -> str:
    normalized = str(prompt_id or "").strip()
    if not normalized:
        raise ValidationError("prompt_id must be a non-empty string.")
    template = load_system_prompts_catalog().text_prompt_templates_v1.get(normalized)
    if template is None:
        raise ValidationError("Unknown prompt template id.")
    return template.render(mapping)
