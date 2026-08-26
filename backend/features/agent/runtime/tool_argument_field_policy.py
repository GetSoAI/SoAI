"""SoAI - Agent tool argument field policy [backend/features/agent/runtime/tool_argument_field_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.truncation import SOAI_TRUNCATION_MARKER, SOAI_TRUNCATION_MARKER_TEXT

__all__ = (
    "CONTENT_ARGUMENT_FIELD_KEYS",
    "IDENTITY_ARGUMENT_FIELD_KEYS",
    "string_contains_internal_truncation_marker",
)

CONTENT_ARGUMENT_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "cmd",
        "command",
        "content",
        "html",
        "input",
        "markdown",
        "patch",
        "prompt",
        "response",
        "stderr",
        "stdout",
        "text",
    },
)
IDENTITY_ARGUMENT_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "file_path",
        "method",
        "name",
        "path",
        "tool",
        "url",
    },
)


def string_contains_internal_truncation_marker(value: str) -> bool:
    return SOAI_TRUNCATION_MARKER_TEXT in value or SOAI_TRUNCATION_MARKER in value
