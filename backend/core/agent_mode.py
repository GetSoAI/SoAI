"""SoAI - Agent mode normalization helpers [backend/core/agent_mode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_agent_mode_or_none",
    "is_agent_mode",
    "is_plan_or_execute_agent_mode",
    "normalize_agent_mode",
)

PLAN_OR_EXECUTE_AGENT_MODE_VALUES: tuple[Literal["plan", "execute"], ...] = (
    "plan",
    "execute",
)


def coerce_agent_mode_or_none(value: JSONValue) -> Literal["chat", "plan", "execute"] | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == "chat":
        return "chat"
    if normalized == "plan":
        return "plan"
    if normalized == "execute":
        return "execute"
    return None


def is_agent_mode(value: JSONValue) -> bool:
    return coerce_agent_mode_or_none(value) is not None


def is_plan_or_execute_agent_mode(value: JSONValue) -> bool:
    normalized = coerce_agent_mode_or_none(value)
    return normalized in PLAN_OR_EXECUTE_AGENT_MODE_VALUES


def normalize_agent_mode(value: JSONValue, *, strict: bool) -> Literal["chat", "plan", "execute"]:
    if value is None:
        return "chat"
    normalized = coerce_agent_mode_or_none(value)
    if normalized is not None:
        return normalized
    if isinstance(value, str) and not value.strip():
        return "chat"
    if strict:
        if isinstance(value, str):
            raise ValidationError("model_settings.agent.mode must be one of: chat, plan, execute.")
        raise ValidationError("model_settings.agent.mode must be a string when provided.")
    return "chat"
