"""SoAI - Agent mode prompt injection [backend/features/agent/runtime/mode_prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.prompt_injection_slots import MODE_TAG, build_injected_prompt_xml
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.openai.internal_message_metadata import (
    AGENT_MODE_MESSAGE_TYPE,
    build_internal_system_message,
)
from core.prompts.system_prompts import get_agent_mode_template_v1

if TYPE_CHECKING:
    from core.agent.settings_types import AgentMode
    from core.types.json import JSONDict

__all__ = (
    "build_mode_system_message",
    "load_mode_template",
)


def load_mode_template(*, mode: AgentMode, tools_visible_to_model: bool) -> str:
    try:
        return get_agent_mode_template_v1(
            mode,
            tools_visible_to_model=tools_visible_to_model,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        raise ValidationError("Failed to load agent mode template.") from exception


def build_mode_system_message(template: str) -> JSONDict:
    content = template.strip()
    if not content:
        raise ValidationError("Agent mode template is empty.")
    wrapped = build_injected_prompt_xml(xml_tag=MODE_TAG, content=content)
    return build_internal_system_message(
        content=wrapped,
        message_type=AGENT_MODE_MESSAGE_TYPE,
    )
