"""SoAI - WebSocket OpenAI images result collection [backend/features/api/routes/system/events/websocket_openai_images/result_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.types.json_value import coerce_json_dict
from features.api.routes.system.events.websocket_openai_result_collection import (
    collect_openai_ws_result,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("collect_openai_image_generation_result",)


async def collect_openai_image_generation_result(
    *,
    reply_queue: asyncio.Queue[Event],
    timeout_seconds: float,
) -> JSONDict:
    result = await collect_openai_ws_result(
        registry=None,
        task_id=None,
        reply_queue=reply_queue,
        timeout_seconds=timeout_seconds,
        timeout_message="Image generation timed out.",
        timeout_operation="ws_openai_images.collect",
        include_payload_event=False,
        finalization_result_builder=None,
    )
    result_dict = coerce_json_dict(result)
    if result_dict is None:
        raise ValidationError("Image generation result must be a JSON object.")
    return result_dict
