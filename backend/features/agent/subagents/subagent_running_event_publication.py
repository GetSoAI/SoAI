"""SoAI - Subagent running realtime event publication [backend/features/agent/subagents/subagent_running_event_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.text_delta_chunking import split_text_delta
from features.agent.runtime.turn_engine import publish_agent_event
from features.agent.subagents.event_payloads import (
    build_subagent_event_payload,
    build_subagent_running_event,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.execution.protocols import SubagentSnapshot
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("publish_subagent_running_event",)


async def publish_subagent_running_event(
    *,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    snapshot: SubagentSnapshot,
    user_id: int,
    conv_id: str,
    result_text: str | None,
    result_text_delta: str | None,
    error_message: str | None,
    token_usage: JSONDict | None,
    updated_at_ms_override: int | None = None,
) -> None:
    event_payload = build_subagent_event_payload(
        snapshot=snapshot,
        user_id=user_id,
        conv_id=conv_id,
        result_text=result_text,
        error_message=error_message,
        token_usage=token_usage,
        updated_at_ms_override=updated_at_ms_override,
    )
    delta_chunks = split_text_delta(result_text_delta)
    if not delta_chunks:
        await publish_agent_event(
            event_bus=event_bus,
            logger=logger,
            event_obj=build_subagent_running_event(
                payload=event_payload,
                result_text_delta=None,
                result_text=event_payload.result_text,
            ),
        )
        return
    for index, delta_chunk in enumerate(delta_chunks):
        await publish_agent_event(
            event_bus=event_bus,
            logger=logger,
            event_obj=build_subagent_running_event(
                payload=event_payload,
                result_text_delta=delta_chunk,
                result_text=event_payload.result_text if index == 0 else None,
            ),
        )
