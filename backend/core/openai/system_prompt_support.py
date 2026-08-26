"""SoAI - Chat system-prompt preparation and injection [backend/core/openai/system_prompt_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.openai.internal_message_metadata import (
    INJECTED_SOAI_MESSAGE_TYPES,
    build_internal_system_message,
    has_internal_message_type,
)
from core.prompts.system_prompts import get_text_prompt_v1
from core.runtime.request_sources import REQUEST_SOURCE_OPENAI, RequestSource

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "detect_timezone_label",
    "find_first_non_system_index",
    "insert_system_message",
    "read_soai_system_prompt_mode",
    "render_identity_display_names",
    "resolve_platform_label",
    "should_inject_soai_system_prompt",
    "strip_injected_soai_messages",
)


def _identity_prefix_user() -> str:
    return get_text_prompt_v1("chat.identity.prefix_user.v1")


def _identity_prefix_assistant() -> str:
    return get_text_prompt_v1("chat.identity.prefix_assistant.v1")


def read_soai_system_prompt_mode(config: ConfigProtocol) -> str:
    raw = config.get("API.OPENAI.PROMPTS.SOAI_SYSTEM_PROMPT_MODE", "auto")
    if not isinstance(raw, str):
        raise ValidationError("API.OPENAI.PROMPTS.SOAI_SYSTEM_PROMPT_MODE must be a string.")
    normalized = raw.strip().lower()
    if normalized in ("auto", "enabled", "disabled"):
        return normalized
    raise ValidationError(f"Unsupported API.OPENAI.PROMPTS.SOAI_SYSTEM_PROMPT_MODE value: {raw!r}.")


def should_inject_soai_system_prompt(
    *,
    config_mode: str,
    request_source: RequestSource,
    conversation_toggle_enabled: bool,
) -> bool:
    if request_source == REQUEST_SOURCE_OPENAI:
        return False
    if config_mode == "disabled":
        return False
    if config_mode == "enabled":
        return True
    return conversation_toggle_enabled


def strip_injected_soai_messages(messages: list[JSONDict]) -> None:
    filtered: list[JSONDict] = []
    for message in messages:
        if not isinstance(message, dict):
            filtered.append(message)
            continue
        if message.get("role") == "system" and has_internal_message_type(
            message,
            INJECTED_SOAI_MESSAGE_TYPES,
        ):
            continue
        filtered.append(message)
    messages[:] = filtered


def render_identity_display_names(
    *,
    user_name: str | None,
    assistant_name: str | None,
) -> str | None:
    lines: list[str] = []
    prefix_user = _identity_prefix_user()
    prefix_assistant = _identity_prefix_assistant()
    if user_name is not None and user_name.strip():
        lines.append(f"{prefix_user.rstrip()} {user_name.strip()}")
    if assistant_name is not None and assistant_name.strip():
        lines.append(f"{prefix_assistant.rstrip()} {assistant_name.strip()}")
    if not lines:
        return None
    return "\n".join(lines)


def insert_system_message(
    messages: list[JSONDict],
    content: str,
    *,
    index: int,
    message_type: str | None = None,
) -> None:
    normalized_content = content.strip()
    if not normalized_content:
        return
    if message_type is None:
        message: JSONDict = {"role": "system", "content": normalized_content}
    else:
        message = build_internal_system_message(
            content=normalized_content,
            message_type=message_type,
        )
    messages.insert(index, message)


def find_first_non_system_index(messages: list[JSONDict]) -> int:
    for index, message in enumerate(messages):
        role = message.get("role") if isinstance(message, dict) else None
        if role != "system":
            return index
    return len(messages)


def detect_timezone_label(now: datetime) -> str:
    tzinfo = now.tzinfo
    name = tzinfo.key if isinstance(tzinfo, ZoneInfo) else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    name = tzinfo.tzname(now) if tzinfo is not None else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "local"


def resolve_platform_label() -> str:
    system_name = platform.system().strip()
    release_name = platform.release().strip()
    machine_name = platform.machine().strip()
    system_part = system_name or "Unknown"
    if release_name:
        system_part = f"{system_part} {release_name}"
    if machine_name:
        return f"{system_part} ({machine_name})"
    return system_part
