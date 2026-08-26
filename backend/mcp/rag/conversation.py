"""SoAI - MCP RAG conversation ID resolution [backend/mcp/rag/conversation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, SoAIError, StateError, ValidationError
from core.users.user_id import is_strict_user_id

if TYPE_CHECKING:
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "cache_get",
    "cache_set",
    "conv_id_candidates",
    "resolve_conv_id_for_user",
)


def conv_id_candidates(conv_id: str) -> list[str]:
    raw = conv_id.strip()
    candidates: list[str] = []

    def _add(value: str) -> None:
        value = value.strip()
        if not value:
            return
        candidates.append(value)

    _add(raw)
    if raw.startswith("conv_"):
        tail = raw[len("conv_") :]
        _add(tail)
        if "-" in tail:
            _add(f"conv_{tail.replace('-', '')}")
    else:
        _add(f"conv_{raw}")
        if "-" in raw:
            _add(raw.replace("-", ""))
            _add(f"conv_{raw.replace('-', '')}")
    try:
        uuid_value = uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        uuid_value = None
    if uuid_value is not None:
        _add(f"conv_{uuid_value.hex}")
    if raw.startswith("conv_"):
        tail = raw[len("conv_") :]
        try:
            uuid_value = uuid.UUID(tail)
        except (ValueError, AttributeError, TypeError):
            uuid_value = None
        if uuid_value is not None:
            _add(f"conv_{uuid_value.hex}")
    return list(dict.fromkeys(candidates))


def cache_get(self: MCPRAGInternalProtocol, key: tuple[int, str]) -> str | None:
    if int(self.cache_max_size) <= 0:
        self.conv_id_resolution_cache.clear()
        return None
    entry = self.conv_id_resolution_cache.get(key)
    if entry:
        value, cached_at_monotonic = entry
        if time.monotonic() - cached_at_monotonic < self.cache_ttl_sec:
            return value
        del self.conv_id_resolution_cache[key]
    return None


def cache_set(self: MCPRAGInternalProtocol, key: tuple[int, str], value: str) -> None:
    max_cache_size = max(0, int(self.cache_max_size))
    if max_cache_size <= 0:
        return
    if len(self.conv_id_resolution_cache) >= max_cache_size:
        excess_entries = (len(self.conv_id_resolution_cache) - max_cache_size) + 1
        evict_count = max(1, max_cache_size // 10, excess_entries)
        sorted_keys = sorted(
            self.conv_id_resolution_cache.keys(),
            key=lambda cache_key: self.conv_id_resolution_cache[cache_key][1],
        )
        for cache_key in sorted_keys[:evict_count]:
            del self.conv_id_resolution_cache[cache_key]
    self.conv_id_resolution_cache[key] = (value, time.monotonic())


async def resolve_conv_id_for_user(self: MCPRAGInternalProtocol, conv_id: str, user_id: int) -> str:
    if not isinstance(conv_id, str) or not conv_id.strip():
        raise ValidationError("conv_id must be a non-empty string")
    normalized_conv_id = conv_id.strip()
    if not isinstance(user_id, int):
        raise ValidationError(f"user_id must be an integer, got {type(user_id).__name__}")
    is_admin_mode = user_id == 0
    if not is_admin_mode and not is_strict_user_id(user_id):
        raise ValidationError(f"user_id must be a positive integer, got {user_id!r}")
    if is_admin_mode:
        candidates = conv_id_candidates(normalized_conv_id)
        return candidates[0] if candidates else normalized_conv_id
    cache_key = (user_id, normalized_conv_id)
    cached = cache_get(self, cache_key)
    if cached:
        return cached
    candidates = conv_id_candidates(normalized_conv_id)
    for candidate in candidates:
        cache_hit = cache_get(self, (user_id, candidate))
        if cache_hit:
            cache_set(self, cache_key, cache_hit)
            return cache_hit
        try:
            conv = await self.database_conversations.get_conversation(candidate, user_id)
        except (
            SoAIError,
            RuntimeError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            raise StateError(f"Failed to validate conv_id for user: {error}") from error
        if conv:
            resolved = str(conv.get("id") or candidate)
            for key in dict.fromkeys([normalized_conv_id, *candidates, resolved]):
                cache_set(self, (user_id, str(key)), resolved)
            return resolved
    raise NotFoundError(
        f"Conversation not found for user_id={user_id}: {normalized_conv_id!r}. Expected a SoAI conversation id such as 'conv_<uuid>' (default is 'conv_<uuidhex>').",
    )
