"""SoAI - WebSocket OpenAI runner failure handling [backend/features/api/routes/system/events/websocket_openai_runner_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.public_projection import project_public_error
from core.orchestrator.protocols_lifecycle import InferenceAdmissionReceipt
from features.api.routes.system.events.internal_protocols import (
    OpenAiWsErrorPayloadBuilder,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.events.types_base import Event
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )

__all__ = (
    "enqueue_openai_ws_reply_channel_unavailable",
    "enqueue_openai_ws_runner_error_payload",
    "openai_ws_detach_event_is_set",
    "resolve_openai_ws_reply_queue_or_enqueue_unavailable",
)


def openai_ws_detach_event_is_set(detach_event: asyncio.Event | None) -> bool:
    return detach_event is not None and detach_event.is_set()


def enqueue_openai_ws_runner_error_payload(
    *,
    coerced: SoAIError,
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    warn_label: str,
    build_error_payload: OpenAiWsErrorPayloadBuilder,
    run_id: str,
    task_id: str | None,
) -> SoAIError:
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        queue,
        build_error_payload(
            run_id=run_id,
            message=project_public_error(coerced).message,
            code=str(coerced.code),
            task_id=task_id,
        ),
        warn_label,
    )
    return coerced


def enqueue_openai_ws_reply_channel_unavailable(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    warn_label: str,
    build_error_payload: OpenAiWsErrorPayloadBuilder,
    run_id: str,
    task_id: str,
    message: str,
) -> None:
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        queue,
        build_error_payload(
            run_id=run_id,
            message=message,
            code="service_unavailable",
            task_id=task_id,
        ),
        warn_label,
    )


def resolve_openai_ws_reply_queue_or_enqueue_unavailable(
    *,
    receipt: InferenceAdmissionReceipt,
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    warn_label: str,
    build_error_payload: OpenAiWsErrorPayloadBuilder,
    run_id: str,
    message: str,
) -> asyncio.Queue[Event] | None:
    reply_queue = receipt.reply_queue
    if reply_queue is not None:
        return reply_queue
    enqueue_openai_ws_reply_channel_unavailable(
        enqueue_warning_tracker,
        queue,
        warn_label,
        build_error_payload,
        run_id,
        receipt.task.task_id,
        message,
    )
    return None
