"""SoAI - OpenAI request message field contracts [backend/core/openai/message_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "OPENAI_MESSAGE_FIELDS_COMMON",
    "OPENAI_MESSAGE_FIELDS_REQUEST",
)

OPENAI_MESSAGE_FIELDS_COMMON: frozenset[str] = frozenset(
    (
        "role",
        "content",
        "name",
        "tool_calls",
        "tool_call_id",
        "refusal",
        "audio",
    ),
)
OPENAI_MESSAGE_FIELDS_REQUEST: frozenset[str] = frozenset(
    (
        *OPENAI_MESSAGE_FIELDS_COMMON,
        "function_call",
    ),
)
