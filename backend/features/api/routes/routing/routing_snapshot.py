"""SoAI - Routing configuration snapshot fetcher shared by REST and WebSocket handlers [backend/features/api/routes/routing/routing_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_models_routing_commands import GetRoutingConfigCommand
from core.events.types_plugins import ErrorEvent
from core.serialization.json import normalize_for_json
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = ("fetch_routing_config_snapshot",)


async def fetch_routing_config_snapshot(
    *,
    event_bus: EventBusProtocol,
    context: RequestContext | None,
) -> JSONDict:
    reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=32)
    await event_bus.publish(GetRoutingConfigCommand(reply_channel=reply_queue, context=context))
    result = await asyncio.wait_for(reply_queue.get(), timeout=RESPONSIVE_TIMEOUT_SEC)
    if isinstance(result, ErrorEvent):
        raise StateError(
            result.message,
            operation="api_routing.fetch_routing_config_snapshot",
        )
    normalized = normalize_for_json(result)
    snapshot = coerce_json_dict(normalized)
    if snapshot is None:
        raise StateError(
            "Routing config snapshot response is invalid.",
            operation="api_routing.fetch_routing_config_snapshot",
        )
    return snapshot
