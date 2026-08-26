"""SoAI - Conversation agent settings update guard [backend/features/api/routes/webui/conversation_agent_settings_update_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.iteration_limits import resolve_agent_max_iterations
from core.model_settings.normalization import normalize_agent_settings
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("require_agent_settings_update_allowed",)


async def require_agent_settings_update_allowed(
    *,
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    existing_settings: JSONDict,
    next_settings: JSONDict,
) -> None:
    existing_agent = normalize_agent_settings(existing_settings.get("agent"))
    next_agent = normalize_agent_settings(next_settings.get("agent"))
    if resolve_agent_max_iterations(existing_agent) == resolve_agent_max_iterations(next_agent):
        return
    snapshot = await api_context.dependencies.chat_stream_registry.snapshot(
        user_id=user_id,
        conv_id=conv_id,
    )
    if snapshot.runtime is not None or snapshot.reservation is not None:
        raise_invalid_request(
            request,
            "Agent max iterations cannot be changed while this conversation is running.",
            error_type="conversation_agent_settings_locked",
        )
    running_turn = await api_context.dependencies.database_agent_turns.get_running_root_turn(
        conv_id=conv_id,
        user_id=user_id,
    )
    if running_turn is not None:
        raise_invalid_request(
            request,
            "Agent max iterations cannot be changed while this conversation has a running agent turn.",
            error_type="conversation_agent_settings_locked",
        )
