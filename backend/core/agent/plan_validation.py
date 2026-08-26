"""SoAI - Long plan normalization and validation [backend/core/agent/plan_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = (
    "MAX_AGENT_PLAN_MARKDOWN_LENGTH",
    "MAX_AGENT_PLAN_TITLE_LENGTH",
    "normalize_plan_markdown",
    "normalize_plan_title",
)

MAX_AGENT_PLAN_TITLE_LENGTH: int = 120
MAX_AGENT_PLAN_MARKDOWN_LENGTH: int = 50_000


def normalize_plan_title(value: JSONValue, *, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("title must be a string when provided.")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > int(max_length):
        raise ValidationError(f"title must be at most {int(max_length)} characters.")
    return stripped


def normalize_plan_markdown(value: JSONValue, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        raise ValidationError("markdown must be a string.")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > int(max_length):
        raise ValidationError(f"markdown must be at most {int(max_length)} characters.")
    return stripped
