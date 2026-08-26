"""SoAI - MCP owner key protocol helpers [backend/core/mcp/owner_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.users.user_id import is_strict_user_id

__all__ = (
    "BROWSER_OWNER_SEGMENT",
    "OPENAI_OWNER_PREFIX",
    "OpenAIOwnerKey",
    "build_browser_owner_key_value",
    "build_openai_conversation_owner_key",
    "build_openai_user_owner_key",
    "parse_openai_conversation_owner_key",
    "parse_openai_owner_key",
)

OPENAI_OWNER_PREFIX = "openai"
BROWSER_OWNER_SEGMENT = "browser"


@dataclass(frozen=True, slots=True)
class OpenAIOwnerKey:
    user_id: int
    conv_id: str | None


def build_openai_user_owner_key(*, user_id: int) -> str:
    if not is_strict_user_id(user_id):
        raise ValidationError("OpenAI owner user_id must be a strict user id.")
    return f"{OPENAI_OWNER_PREFIX}:{user_id}"


def build_openai_conversation_owner_key(*, user_id: int, conv_id: str) -> str:
    normalized_conv_id = conv_id.strip()
    if not normalized_conv_id:
        raise ValidationError("OpenAI conversation owner conv_id must be non-empty.")
    return f"{build_openai_user_owner_key(user_id=user_id)}:{normalized_conv_id}"


def parse_openai_owner_key(owner_key: str) -> OpenAIOwnerKey | None:
    normalized = owner_key.strip()
    if not normalized:
        return None
    parts = normalized.split(":", 2)
    if len(parts) not in (2, 3) or parts[0] != OPENAI_OWNER_PREFIX:
        return None
    user_id_text = parts[1].strip()
    if not user_id_text:
        return None
    try:
        user_id = int(user_id_text)
    except ValueError:
        return None
    if not is_strict_user_id(user_id):
        return None
    if len(parts) == 2:
        return OpenAIOwnerKey(user_id=user_id, conv_id=None)
    conv_id = parts[2].strip()
    if not conv_id:
        return None
    return OpenAIOwnerKey(user_id=user_id, conv_id=conv_id)


def parse_openai_conversation_owner_key(owner_key: str) -> OpenAIOwnerKey | None:
    parsed = parse_openai_owner_key(owner_key)
    if parsed is None or parsed.conv_id is None:
        return None
    return parsed


def build_browser_owner_key_value(
    *,
    owner_base: str,
    profile_slug: str,
    session_scope_slug: str,
) -> str:
    base = owner_base.strip()
    profile = profile_slug.strip()
    session_scope = session_scope_slug.strip()
    if not base:
        raise ValidationError("Browser owner base must be non-empty.")
    if not profile:
        raise ValidationError("Browser profile slug must be non-empty.")
    if not session_scope:
        raise ValidationError("Browser session scope slug must be non-empty.")
    return f"{base}:{BROWSER_OWNER_SEGMENT}:{profile}:scope:{session_scope}"
