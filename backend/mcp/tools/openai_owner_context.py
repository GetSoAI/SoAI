"""SoAI - MCP tool OpenAI owner context parsing [backend/mcp/tools/openai_owner_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.owner_keys import parse_openai_conversation_owner_key
from mcp.tools.error import build_invalid_params_error

__all__ = ("has_openai_conversation_owner", "require_openai_conversation_owner")


def has_openai_conversation_owner(owner_key: str) -> bool:
    return parse_openai_conversation_owner_key(owner_key) is not None


def require_openai_conversation_owner(owner_key: str, *, tool_name: str) -> tuple[int, str]:
    normalized = owner_key.strip() if isinstance(owner_key, str) else ""
    message = f"{tool_name} requires an OpenAI conversation owner context."
    parsed = parse_openai_conversation_owner_key(normalized)
    if parsed is None or parsed.conv_id is None:
        raise build_invalid_params_error(message)
    return (parsed.user_id, parsed.conv_id)
