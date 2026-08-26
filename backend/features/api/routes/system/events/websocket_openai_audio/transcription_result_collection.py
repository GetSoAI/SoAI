"""SoAI - WebSocket OpenAI transcription result collection [backend/features/api/routes/system/events/websocket_openai_audio/transcription_result_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.types.json import is_json_dict
from features.api.routes.system.events.websocket_openai_result_collection import (
    collect_openai_ws_result,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("collect_openai_transcription_result",)


def _build_transcription_finalization_result(payload: JSONValue) -> JSONDict:
    if is_json_dict(payload):
        return payload
    return {"result": payload}


async def collect_openai_transcription_result(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    timeout_seconds: float,
) -> JSONValue:
    return await collect_openai_ws_result(
        registry=registry,
        task_id=task_id,
        reply_queue=reply_queue,
        timeout_seconds=timeout_seconds,
        timeout_message="Audio transcription timed out.",
        timeout_operation="ws_openai_audio.transcription.collect",
        include_payload_event=True,
        finalization_result_builder=_build_transcription_finalization_result,
    )
