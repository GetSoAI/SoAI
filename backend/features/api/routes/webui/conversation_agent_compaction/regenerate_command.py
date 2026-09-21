"""SoAI - Manual compaction regeneration command identity [backend/features/api/routes/webui/conversation_agent_compaction/regenerate_command.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict
from features.api.schemas.conversations import AgentCompactionRegenerateRequest

__all__ = (
    "build_manual_compaction_regeneration_command",
    "serialize_manual_compaction_regeneration_command",
)


def build_manual_compaction_regeneration_command(
    payload: AgentCompactionRegenerateRequest,
) -> JSONDict | None:
    if payload.client_id is None:
        return None
    return {
        "assistant_turn_at_ms": int(payload.assistant_turn_at_ms),
        "client_id": payload.client_id,
        "client_request_id": payload.client_request_id,
        "expected_last_modified_at_ms": payload.expected_last_modified_at_ms,
    }


def serialize_manual_compaction_regeneration_command(
    payload: AgentCompactionRegenerateRequest,
) -> str | None:
    command = build_manual_compaction_regeneration_command(payload)
    return serialize_json_compact_stable(command) if command is not None else None
