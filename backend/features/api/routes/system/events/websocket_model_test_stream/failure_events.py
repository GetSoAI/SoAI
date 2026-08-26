"""SoAI - WebSocket model test stream failure events [backend/features/api/routes/system/events/websocket_model_test_stream/failure_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.public_projection import project_public_error
from core.timing.monotonic import monotonic_ms
from features.api.routes.system.events.websocket_model_test_stream.state import (
    ModelTestStreamRuntime,
    publish_model_test_stream_event,
    publish_model_test_stream_loading_activity,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = ("publish_model_test_stream_error",)


async def publish_model_test_stream_error(
    *,
    event_bus: EventBusProtocol,
    runtime: ModelTestStreamRuntime,
    exception: SoAIError,
) -> None:
    duration_ms = max(0, monotonic_ms() - runtime.started_at_ms)
    public_error = project_public_error(exception)
    await publish_model_test_stream_loading_activity(
        event_bus,
        runtime,
        status="error",
        duration_ms=duration_ms,
        reason=public_error.message,
        error_type=str(public_error.code),
    )
    await publish_model_test_stream_event(
        event_bus,
        runtime,
        event_type="error",
        payload={"message": public_error.message, "code": str(public_error.code)},
    )
